#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run one alert-monitor cycle for GitHub Actions or cron-like runners."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger("alert_monitor_once")
GITHUB_ALERT_RULE_SOURCE = "github_alert"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: Optional[int] = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw, default)
        return default
    if minimum is not None and value < minimum:
        logger.warning("Invalid %s=%r; using %s", name, raw, default)
        return default
    return value


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def _us_market_is_open_now() -> bool:
    from src.core.trading_calendar import MarketPhase, build_market_phase_context

    context = build_market_phase_context(
        market="us",
        trigger_source="github_alert_workflow",
    )
    logger.info(
        "US market phase=%s local_time=%s trading_day=%s open_now=%s warnings=%s",
        context.phase.value,
        context.market_local_time.isoformat(),
        context.is_trading_day,
        context.is_market_open_now,
        ",".join(context.warnings) or "-",
    )
    return context.phase in {MarketPhase.INTRADAY, MarketPhase.CLOSING_AUCTION}


def _row_semantic_key(service: Any, row: Any) -> str:
    data = service._serialize_rule_base(row)
    return service._semantic_key(
        data["target_scope"],
        data["target"],
        data["alert_type"],
        data["parameters"],
    )


def _list_rules(service: Any, **filters: Any) -> List[Any]:
    rows, _total = service.repo.list_rules(page=1, page_size=1000, **filters)
    return list(rows)


def _active_status(entry: Dict[str, Any]) -> bool:
    status = str(entry.get("status") or "active").strip().lower()
    return status == "active"


def _legacy_rule_payload(
    service: Any,
    entry: Dict[str, Any],
    *,
    cooldown_seconds: int,
) -> Tuple[str, Dict[str, Any]]:
    from src.agent.events import validate_event_alert_rule

    validate_event_alert_rule(entry)
    target = str(entry.get("stock_code") or "").strip()
    alert_type = str(entry.get("alert_type") or "").strip().lower()
    parameters = service._normalize_parameters(alert_type, entry)
    semantic_key = service._semantic_key("single_symbol", target, alert_type, parameters)
    payload = {
        "name": f"GitHub alert | {target} {alert_type}",
        "target_scope": "single_symbol",
        "target": target,
        "alert_type": alert_type,
        "parameters": parameters,
        "severity": str(entry.get("severity") or "warning").strip().lower(),
        "enabled": True,
        "cooldown_policy": {"cooldown_seconds": cooldown_seconds},
    }
    return semantic_key, payload


def _sync_legacy_env_rules_to_db(config: Any, *, cooldown_seconds: int) -> Dict[str, int]:
    """Mirror legacy JSON env rules into DB rules so cooldown survives CI runs."""
    from src.agent.events import parse_event_alert_rules
    from src.services.alert_service import AlertService

    service = AlertService()
    raw_rules = getattr(config, "agent_event_alert_rules_json", "") or ""
    parsed_rules = parse_event_alert_rules(raw_rules)

    github_rows = _list_rules(service, source=GITHUB_ALERT_RULE_SOURCE)
    github_by_key = {_row_semantic_key(service, row): row for row in github_rows}

    enabled_rows = _list_rules(service, enabled=True)
    enabled_keys = {_row_semantic_key(service, row) for row in enabled_rows}

    desired_active_keys = set()
    created = 0
    updated = 0
    skipped = 0
    disabled = 0

    for index, entry in enumerate(parsed_rules, start=1):
        if not isinstance(entry, dict):
            logger.warning("Skip legacy alert rule #%d: not an object", index)
            skipped += 1
            continue

        try:
            semantic_key, payload = _legacy_rule_payload(
                service,
                entry,
                cooldown_seconds=cooldown_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - keep one bad rule from blocking all.
            logger.warning("Skip invalid legacy alert rule #%d: %s", index, exc)
            skipped += 1
            continue

        if not _active_status(entry):
            continue

        desired_active_keys.add(semantic_key)
        existing_github_row = github_by_key.get(semantic_key)
        if existing_github_row is not None:
            fields = service._normalize_rule_payload(payload, source=GITHUB_ALERT_RULE_SOURCE)
            service.repo.update_rule(int(existing_github_row.id), fields)
            updated += 1
            continue

        if semantic_key in enabled_keys:
            logger.info("Alert rule already exists outside GitHub sync: %s", semantic_key)
            skipped += 1
            continue

        fields = service._normalize_rule_payload(payload, source=GITHUB_ALERT_RULE_SOURCE)
        row = service.repo.create_rule(fields)
        github_by_key[semantic_key] = row
        enabled_keys.add(semantic_key)
        created += 1

    for semantic_key, row in github_by_key.items():
        if semantic_key in desired_active_keys:
            continue
        if bool(getattr(row, "enabled", False)):
            service.repo.update_rule(int(row.id), {"enabled": False})
            disabled += 1

    return {
        "parsed": len(parsed_rules),
        "created": created,
        "updated": updated,
        "disabled": disabled,
        "skipped": skipped,
    }


def _run_worker_once() -> Dict[str, int]:
    from src.config import Config, get_config
    from src.services.alert_worker import AlertWorker

    Config.reset_instance()
    config = get_config()
    worker = AlertWorker(config_provider=lambda: get_config())
    return worker.run_once()


def run(force: bool) -> int:
    from src.config import Config, get_config

    if not force and not _us_market_is_open_now():
        logger.info("Skip alert monitor: US regular market is not open.")
        return 0

    Config.reset_instance()
    config = get_config()
    if not getattr(config, "agent_event_monitor_enabled", False):
        logger.info("Skip alert monitor: AGENT_EVENT_MONITOR_ENABLED is not true.")
        return 0

    if _env_bool("ALERT_WORKFLOW_SYNC_LEGACY_TO_DB", True):
        cooldown_seconds = _env_int("ALERT_WORKFLOW_COOLDOWN_SECONDS", 24 * 60 * 60, minimum=0)
        sync_stats = _sync_legacy_env_rules_to_db(config, cooldown_seconds=cooldown_seconds)
        logger.info("GitHub alert rule sync: %s", json.dumps(sync_stats, ensure_ascii=False, sort_keys=True))

    stats = _run_worker_once()
    logger.info("Alert worker stats: %s", json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run one alert-monitor cycle.")
    parser.add_argument(
        "--force",
        action="store_true",
        default=_env_bool("ALERT_WORKFLOW_FORCE_RUN", False),
        help="Run even when the US regular market is not currently open.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    _configure_logging()
    return run(force=bool(args.force))


if __name__ == "__main__":
    raise SystemExit(main())
