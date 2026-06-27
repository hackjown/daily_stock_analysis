# PR #1778 前后对比证据（真实端到端截图）

本目录截图均来自真实代码路径：Web 端是 `apps/dsa-web` 构建产物（`npm run build` →
`static/`）通过 Playwright 拦截 `/api/v1/*` 渲染真实 React 组件；推送报告由
`src/notification.py` 真实生成，并经 `src/formatters.markdown_to_html_document`
渲染为 HTML 截图。生成脚本保留在 `local/pr1778-evidence/`，不入库。

## 一、Web 首页 大盘复盘视图

入口：dsa-web 首页 → 点击「大盘复盘」按钮 → 后端返回 `market_review_payload` 后渲染
`MarketReviewReportView` 的「结构化大盘数据」卡片。

- **修复前**（PR #1778 未应用，`market_review_payload` 中没有 `concepts` 字段）：
  - 截图：`pr-1778-home-real-before-zh.png`
  - 卡片只渲染「行业板块 · 领涨 / 领跌」两栏，没有概念板块。
- **修复后**（PR #1778 + 左右并列布局修复）：
  - 截图：`pr-1778-home-real-after-zh.png`
  - 「行业板块」与「概念板块」上下两行各自左右并列；右侧空位被充分利用，
    机器人概念 +4.20%、AI算力 +3.85% 等清晰展示。

并列布局来自 `apps/dsa-web/src/components/report/MarketReviewReportView.tsx` 同
PR 的修复 commit（`fix: render market review industry and concept rankings side-by-side`，
合入 `autocode/issue-1764-feat-web`）。

## 二、推送报告（Daily Dashboard）

入口：`NotificationService.generate_dashboard_report(results, report_date=...)`，
即每日批量分析后推送到飞书 / Telegram / 邮件 的完整决策仪表盘。差异集中在每只个股的
「🧩 关联板块」表格，受 `_append_related_boards` 控制。

- **修复前**：`fundamental_context` 中没有 `concept_boards`，关联板块表里概念板块只剩
  「板块 | 类型」两列，缺失「板块表现 / 板块涨跌幅」。腾讯控股的 AI算力 / 机器人概念
  无法看到当日热度。
  - 截图：`pr-1778-push-daily-before-zh.png`
- **修复后**：`DataFetcherManager.get_concept_rankings()` 注入 `concept_boards`
  后，同一段代码把「板块表现」「板块涨跌幅」补齐：
  AI算力 → 领涨 +3.85%、机器人概念 → 领涨 +4.20%。
  - 截图：`pr-1778-push-daily-after-zh.png`

## 三、推送报告（单股 Simple）

入口：`NotificationService.generate_single_stock_report(result)`，触发自分析单只股票
的推送格式。

- **修复前**：`pr-1778-push-stock-before-zh.png`
- **修复后**：`pr-1778-push-stock-after-zh.png`

差异同上：概念板块从「-- | --」变成 `领涨 / +X.XX%`。

## 四、复现命令

证据脚本与中间产物存放在 `local/pr1778-evidence/`（`local/` 已在 `.gitignore` 范围内，
不会入库）：

```powershell
# Web 首页真实端到端截图（嵌入静态文件服务器 + Playwright /api/v1 mock）
$env:MR_MODE = "before"; node local/pr1778-evidence/real-app.mjs
$env:MR_MODE = "after";  node local/pr1778-evidence/real-app.mjs

# 推送报告 BEFORE/AFTER markdown + HTML + 截图
python local/pr1778-evidence/build_daily_report.py
python local/pr1778-evidence/build_notification_md.py
python local/pr1778-evidence/render_md_to_html.py
node    local/pr1778-evidence/screenshot_md.mjs
```
