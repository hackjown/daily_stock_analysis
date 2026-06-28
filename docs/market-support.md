# 市场支持与边界

## 日本/韩国个股 suffix-only MVP（Issue #1718，Refs #1718）

当前阶段支持手动输入日本、韩国股票的 Yahoo Finance 后缀代码，进入既有个股分析、历史保存和基础报告展示链路。Web 自动补全内置一批常用日股/韩股种子索引，支持按 suffix 代码、中英文名称或常用别名搜索。

支持格式：

- 日本：`7203.T`、`6758.T`
- 韩国 KOSPI：`005930.KS`
- 韩国 KOSDAQ：`035720.KQ`

约束与边界：

- 手动输入裸代码时会先检索本地/远程股票池；若 `005930`、`000660` 等裸码命中 `005930.KS`、`000660.KS` 等日韩条目，则按命中的市场提交分析；若股票池未命中，仍按既有 6 位数字代码规则默认落到 A 股语义，并保留为可追踪的跨市场歧义边界。
- 日股/韩股 suffix 识别已集中到共享市场代码工具，数据源路由、Prompt 市场识别、交易日历和股票索引裸码解析复用同一组规则，减少后续市场扩展时的规则漂移。
- 日股/韩股日线和基础实时/近实时行情只走 `YfinanceFetcher`，不尝试 AkShare、Tushare、Efinance、Pytdx、Baostock 等 A 股专属数据源；yfinance 报价会尽量带上 `market`、`currency`、`data_quality`、`missing_fields` 等质量元数据。
- 基本面复用既有 offshore yfinance 轻量路径；A 股专属资金流、龙虎榜、板块等能力按 `not_supported` 降级，offshore 基本面上下文也会标记 provider、as_of、data_quality 和缺失块。
- 报告 Prompt 已增加日股/韩股市场语义，避免套用 A 股涨跌停、北向资金、龙虎榜、融资融券等概念。
- 交易日历注册 `jp: XTKS / Asia/Tokyo` 与 `kr: XKRX / Asia/Seoul`。若本地 `exchange-calendars` 版本缺少对应日历，既有 fail-open/fail-closed 语义保持不变。

兼容性与回退说明（针对结构化检测命中项）：

- `#1815` 本次仅新增 `yfinance` 报价/基本面上下文中的可选字段元数据（如 `market`、`currency`、`data_quality`、`missing_fields`、`provider`），未改动 LLM provider/model/base URL、配置 Schema、运行时环境变量、数据库字段、存量缓存序列化或消息协议版本。
- 与本条 PR 相关的配置语义上，未新增或替换 provider、model、base URL，未新增配置清理/迁移分支；已保存配置仍保持原样，回退方式为回退该提交。
- 外部 API 边界仍仅限既有 `yfinance` fetch 路径（含 `Ticker`/`history`/`fast_info`）与既有兜底逻辑；没有新增或迁移 API 网关/host，`YFINANCE_PRIORITY` 是唯一受影响的可见参数。JP/KR 主指数与 Yahoo symbol 对应如下（可核验）：
  - 日经225：`^N225`（<https://finance.yahoo.com/quote/%5EN225/>）
  - 东证指数：`^TOPX`（<https://finance.yahoo.com/quote/%5ETOPX/>）
  - KOSPI：`^KS11`（<https://finance.yahoo.com/quote/%5EKS11/>）
  - KOSDAQ：`^KQ11`（<https://finance.yahoo.com/quote/%5EKQ11/>）
  - 依赖版本：`requirements.txt` 中 `yfinance>=0.2.0`，回归覆盖路径见 `tests/test_yfinance_jp_kr_indices.py` 与 `tests/test_yfinance_hk_indices.py`。
- 兼容性与回退：`MARKET_REVIEW_REGION` 会保留合法逗号子集（如 `cn,us`）并保持 `both` 全量行为，非法值或空值回退到 `cn`，不会清空或迁移已保存配置。既有 `cn`、`hk`、`us` 可原样保留；若用户希望维持 JP/KR 扩展前 `both` 对应的三市场复盘边界，应改为 `cn,hk,us`；只有希望纳入五市场复盘时才继续使用 `both` 或显式配置 `cn,hk,us,jp,kr`。
- 运行时边界：JP/KR 指数按 market_review 的 fail-open 约定逐项抓取；单项失败不会阻断其余指数与其他市场；当两个市场均无可用主指数行情时返回本地可见 `None/空`，主流程继续可按其余市场输出或直接降级。
- 兼容性验证依据：行情/基本面上下文在 `data_provider/base.py` 与 `realtime_types.py` 中按现有 `getattr`/可选字段约定向下游透传，不强制读写新增字段；无配置迁移脚本，`tests/test_config_env_compat.py::test_market_review_region_updates_do_not_change_llm_provider_model_contract` 已覆盖 `MARKET_REVIEW_REGION` 扩展不改变 LLM provider/model/Base URL 契约。
- 回退方式：若新增元数据字段在某端产生兼容问题，可先忽略这些字段并按既有市场判定+行情展示链路运行；必要时回滚本次提交或通过移除 `jp/kr` `MarketSymbol` 及路由扩展恢复旧行为。

不承诺项：

- 不承诺实时行情；Yahoo Finance 数据可能延迟或字段缺失。
- 不承诺完整基本面、行业/板块、市场宽度或涨跌家数。JP/KR 大盘复盘 v1 仅提供主要指数、新闻线索与模板/LLM 复盘，不提供日韩市场宽度或板块排行。
- 不承诺完整日韩全市场股票列表；Web 自动补全当前仅覆盖仓内种子索引中的常用标的（已扩充至各 30 只左右的头部标的），未命中时仍可手动输入 suffix 代码。
- Portfolio 允许 JP/KR 账户、交易和持仓快照进入现有链路，但会将账户/持仓快照标记为 `data_quality=partial`，并通过 `limitations` 明确 `realtime_quote_best_effort`、`fx_and_cost_basis_partial`、`sector_and_risk_metrics_limited`；不承诺 JPY/KRW 汇率、成本、市值、行业集中度或组合风险指标完整口径。

Phase 3 Portfolio / Market Light 边界补充：

- JP/KR 账户、交易、现金流水和公司行动 API 保持可创建/查询；当前不新增 JPY/KRW 汇率源、税费模型、交易单位/最小变动价位校验或行业映射。
- Market Light 快照和 Market Light 告警仍只支持 `cn` / `hk` / `us`。
- Web 告警市场下拉不展示 `jp` / `kr`；后端 `normalize_market_region()` 对 `jp` / `kr` 返回显式 unsupported 错误。
- Web 设置页中 `MARKET_REVIEW_REGION` 从固定枚举下拉收敛为自由文本输入，用于保存 `cn,us,jp`、`cn,hk,us` 等逗号分隔子集；该 UI 变化只影响大盘复盘配置，不影响 Market Light 告警市场枚举。
- 该轮边界收敛不改动 LLM Provider / Model / Base URL 的持久化语义，也不执行默认模型、运行时配置清理或回写；配置更新仍是**原子 upsert**（`ConfigManager.apply_updates`），保存/导入只写入提交的键，未提交的 `LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS`、`AGENT_LITELLM_MODEL`、`VISION_MODEL`、`OPENAI_BASE_URL` 等旧值保留不清空。
- 可直接核验的配置兼容证据：官方来源没有新增或替换，LiteLLM OpenAI-compatible 路由、OpenAI Chat Completions 与各 provider 官方来源仍沿用 [LLM 配置指南](LLM_CONFIG_GUIDE.md#常用官方文档来源用于核对预设-provider--base-url--模型命名)；当前运行时依赖窗口仍以 `requirements.txt` 的 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<2.0.0` 为准；旧配置没有迁移脚本或清理分支，保存/导入仍只通过 `ConfigManager.apply_updates` 写入本次提交键。回退路径是恢复变更前 `.env`/配置备份中的 `MARKET_REVIEW_REGION`，或直接 revert 本 PR；未提交的 `LITELLM_CONFIG`、`LLM_CHANNELS`、`LLM_OPENAI_*`、`LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS`、`VISION_MODEL`、`OPENAI_*` 等既有运行时配置不需要迁移。回归证据为 `tests/test_system_config_service.py::SystemConfigServiceTestCase::test_update_market_review_region_does_not_trigger_runtime_model_cleanup`。
- Web UI 可视证据口径：Market Light 告警目标范围切到“大盘市场”时，市场区域下拉只显示 A 股、港股、美股，不显示日股/韩股；设置页 `MARKET_REVIEW_REGION` 渲染为可输入逗号分隔值的文本框。当前仓库不保存一次性截图证据，可替代证据为 `apps/dsa-web/src/components/alerts/__tests__/AlertRuleForm.test.tsx`、`apps/dsa-web/src/components/settings/__tests__/SettingsField.test.tsx` 和 `apps/dsa-web/tests/system_config_i18n.test.ts` 的断言。

回滚方式：移除 Portfolio snapshot 的 `data_quality` / `limitations` 扩展，恢复告警前端/后端对市场枚举的旧边界说明；如需整体回滚，移除 `jp/kr` 市场识别、交易日历注册、YFinance 路由扩展、Web/API 类型放行、`scripts/stock_index_seeds/` 日韩种子索引，并删除本文档中的能力声明。

## 台湾个股 suffix-only MVP（Issue #1772，Refs #1772）

当前阶段支持手动输入台湾股票的 Yahoo Finance 后缀代码，进入既有个股分析、历史保存和基础报告展示链路。TWSE 上市股票使用 `.TW` 后缀，TPEx 上柜（柜买）股票使用 `.TWO` 后缀，二者折叠为同一 `tw` 市场标签。**本次覆盖市场识别（detection）、数据路由层、DecisionSignal/Portfolio/Intelligence 服务层与 API 市场枚举，以及 DecisionSignal/Portfolio 前端市场类型与筛选**；台股股票索引/种子、Web 自动补全与告警（大盘红绿灯）市场放行仍作为后续 PR。对齐 #1718 日韩 MVP 模式。

支持格式：

- 上市（TWSE）：`2330.TW`、`0050.TW`
- 上柜（TPEx / 柜买）：`6488.TWO`、`5483.TWO`
- 代码 base 为 4-6 位数字（普通股 4 位，ETF/其他至 6 位，如 `00878.TW`、`006208.TW`），较日股 `.T` 的 4-5 位更宽。

约束与边界：

- **严格 suffix-only**：裸 `2330`、`00878` 等不带后缀的代码不会进入台股语义（`detect_market` / `get_market_for_stock` 仅在显式 `.TW`/`.TWO` 后缀时返回 `tw`）。本次**不引入任何台股股票索引/种子解析**，故裸码不可能经本地/远程股票池被改写为台股 suffix；该索引解析（与 jp/kr 同款的裸码命中行为）属后续 PR。
- 台股日线和基础实时/近实时行情只走 `YfinanceFetcher`，不尝试 AkShare、Tushare、Efinance、Pytdx、Baostock 等 A 股专属数据源。
- 基本面复用既有 offshore yfinance 轻量路径；A 股专属资金流、龙虎榜、板块等能力按 `not_supported` 降级。
- 报告 Prompt 已增加台股市场语义（新台币、三大法人、TWSE/TPEx ±10% 涨跌停），避免套用 A 股北向资金、龙虎榜等概念。
- 交易日历注册 `tw: XTAI / Asia/Taipei`。TWSE 为 09:00–13:30 连续交易、无午休；收盘集合竞价暂不建模，与 jp/kr 一致。若本地 `exchange-calendars` 版本缺少对应日历，既有 fail-open/fail-closed 语义保持不变。
- 主要指数提供加权指数 `^TWII` 与柜买指数 `^TWOII`。

不承诺项：

- 不承诺实时行情；Yahoo Finance 数据可能延迟或字段缺失。
- 不承诺完整基本面、行业/板块、市场宽度、涨跌家数或台股大盘复盘。
- 台股股票索引/种子、Web 自动补全与告警（大盘红绿灯）市场放行仍作为后续 PR；告警 MarketRegion 与后端 market_light 仍为 cn/hk/us，未含 tw。
- 不补齐 Portfolio 的 TWD 汇率、成本、市值完整口径（属上述后续 PR 范围）。

回滚方式：移除 `tw` 市场识别、交易日历注册、YFinance 路由扩展与服务层/API 市场枚举及前端市场类型放行，并删除本文档中的能力声明。
