# Strategy Enable Score System v1.1.0

策略质量评估系统 — 判断已存在策略在当前市场环境下是否应开启（强/中/弱/禁用）。

**当前版本：** v1.1.0 Stable ✅ | **测试：** 230/230 | **Baseline：** 0/3/3/6 (delta=0)

## 快速开始

```bash
cd SSS-Strategy-Score-System
pip install -r requirements.txt
PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml
```

## 运行测试

```bash
PYTHONPATH=src python3 -m pytest tests/ -v
```

## 输入数据

CSV 格式，支持单文件或多文件合并。详见 `data/sample_trades.csv`。

### 真实 CSV 接入步骤

1. **准备 CSV**：确保包含所有必填字段，字段名与 `data/sample_trades.csv` 一致
2. **标签治理**（推荐）：先运行 `PYTHONPATH=src python3 -m strategy_enable_system.label_quality --config config.yaml` 修复 session/structure_state/regime_snapshot_id
3. **放置文件**：将原始 CSV 放入 `data/` 目录
4. **修改配置**：编辑 `config.yaml`，将 `input_path` 改为你的文件路径
   ```yaml
   input_path:
     - "outputs/data_quality/cleaned_trades.csv"
     # 多文件合并：
     # - "data/trades_2025.csv"
     # - "data/trades_2026.csv"
   ```
5. **调整参数**（可选）：根据你的数据量和风险偏好修改 `min_trades`、`drawdown_threshold_R`、`score_thresholds`
6. **运行**：`PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml`
7. **验收**：按 `docs/real_data_validation_checklist.md` 逐项检查输出

> **默认输入：** 当前 `config.yaml` 默认使用 `outputs/data_quality/cleaned_trades.csv`（经 P2-2 标签治理工具修复）。
> 原始真实 CSV 位于 `data/combined_trade_log_20260513.csv`。
> P2-3 已验证 cleaned CSV 与原始 CSV 评分完全一致（delta = 0.000）。

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `trade_id` | string | 唯一交易 ID |
| `strategy_name` | string | 策略名称 |
| `symbol` | string | 交易品种 |
| `direction` | string | `long` 或 `short` |
| `entry_time` | datetime | 入场时间 |
| `exit_time` | datetime | 出场时间 |
| `pnl_R` | float | R 倍数收益（核心统计单位） |
| `session` | string | 交易时段 |
| `regime` | string | 市场 regime 分组 |

### 可选字段

`pnl_usd`、`setup_type`、`volatility_state`、`oi_state`、`cvd_state`、`funding_state`、`coinbase_premium_state`、`etf_flow_state`、`regime_snapshot_id`、`structure_state`、`orderflow_state`、`macro_state`

缺失的可选字段自动填充 `"unknown"`。

## TradingView CSV 转换工具

如果交易记录来自 TradingView Strategy Tester，先转换成系统标准 CSV，再运行 P2-2 标签治理工具。转换器只负责字段映射和 `pnl_R` 计算，不负责判断真实市场标签。

### 推荐流程

1. **转换**：把每个 TradingView CSV 转为标准交易 CSV。
   ```bash
   PYTHONPATH=src python3 -m strategy_enable_system.tradingview_converter \
     --input data/tradingview_export.csv \
     --output data/tradingview_converted.csv \
     --strategy-name "TV_Strategy" \
     --symbol BTCUSDT \
     --regime unknown \
     --risk-usd 100
   ```

2. **治理**：将 `config.yaml input_path` 指向转换后的 CSV，然后运行标签治理。
   ```bash
   PYTHONPATH=src python3 -m strategy_enable_system.label_quality --config config.yaml
   ```

3. **评分**：使用治理后的 `outputs/data_quality/cleaned_trades.csv` 运行主流程。
   ```bash
   PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml
   ```

⚠️ 多个 TradingView 文件合并时必须运行标签治理。TradingView 的 `Trade #` 会从 1 重新编号，多个策略合并后容易出现重复 `trade_id`；标签治理会将重复 ID 命名空间化，并把原始值保留到 `original_trade_id`。

### 可选：单文件转换后自动治理

如果只处理单个 TradingView 文件，可以让转换器额外输出一份 cleaned CSV：

```bash
PYTHONPATH=src python3 -m strategy_enable_system.tradingview_converter \
  --input data/tradingview_export.csv \
  --output data/tradingview_converted.csv \
  --strategy-name "TV_Strategy" \
  --symbol BTCUSDT \
  --regime unknown \
  --risk-usd 100 \
  --apply-label-quality \
  --cleaned-output data/tradingview_converted_cleaned.csv
```

这个选项会自动回填 `session`、`structure_state`、`regime_snapshot_id`，并补齐缺失标签列。多文件场景仍建议使用独立的 `label_quality` 流程统一治理。

### 可选：单文件转换后同时 Enrich

如果本地已经有 CoinGlass processed 数据，也可以在转换后同时生成 enriched CSV。该流程固定为：转换 -> 标签治理 -> enrichment；不会直接对未治理 CSV 做 enrichment。

```bash
PYTHONPATH=src python3 -m strategy_enable_system.tradingview_converter \
  --input data/tradingview_export.csv \
  --output data/tradingview_converted.csv \
  --strategy-name "TV_Strategy" \
  --symbol BTCUSDT \
  --regime unknown \
  --risk-usd 100 \
  --apply-enrichment \
  --enrichment-processed-dir data/external/coinglass/processed \
  --enriched-output data/tradingview_converted_enriched.csv
```

`--apply-enrichment` 会自动额外写出 cleaned CSV。它只读取已经缓存/处理好的外部数据，不会抓取 CoinGlass live API。多文件场景仍建议先统一运行 `label_quality`，再运行独立的 `label_enrichment`。

### 可选：调用 DMC 回测引擎修整 TV 标签

如果 TradingView CSV 缺少回测引擎标签，可以让转换器调用本地 `DMC-Sisie-Quantive` 的 enricher，回填 `session`、`regime`、`regime_snapshot_id`、`structure_state`、`volatility_state`：

```bash
PYTHONPATH=src python3 -m strategy_enable_system.tradingview_converter \
  --input data/tradingview_export.csv \
  --output data/tradingview_converted.csv \
  --strategy-name "TV_Strategy" \
  --symbol BTCUSDT \
  --risk-usd 100 \
  --apply-dmc-labels \
  --dmc-root C:/Users/12645/DMC-Sisie-Quantive \
  --dmc-snapshot-granularity day
```

默认会额外生成：

```text
data/tradingview_converted_dmc_labeled.csv
data/tradingview_converted_dmc_labeled_dmc_bridge_report.md
```

DMC bridge 只负责本地回测引擎能可靠提供的标签，不回填 OI / Funding / CVD / ETF / Macro / Coinbase Premium。

### 可选：转换后自动更新 config.yaml

如果希望转换后自动把结果加入 `config.yaml input_path`，加上 `--update-config-input`：

```bash
PYTHONPATH=src python3 -m strategy_enable_system.tradingview_converter \
  --input data/tradingview_export.csv \
  --output data/tradingview_converted.csv \
  --strategy-name "TV_Strategy" \
  --symbol BTCUSDT \
  --regime unknown \
  --risk-usd 100 \
  --update-config-input \
  --config config.yaml
```

规则：

| 场景 | 写入 `input_path` 的文件 |
|------|--------------------------|
| 普通转换 | `--output` 指定的 converted CSV |
| `--apply-label-quality` | 仍写入 converted CSV，后续建议统一跑 `label_quality` |
| `--apply-dmc-labels` | DMC 修整后的 CSV |
| `--apply-enrichment` | 写入 enriched CSV |

已存在的路径不会重复写入。

### 支持格式

| 格式 | 说明 |
|------|------|
| closed | 一行一笔完整交易，包含 entry/exit time、direction、profit |
| paired | TradingView entry/exit 两行格式，按 trade number 配对 |
| auto | 默认自动识别上述两类 |

### `pnl_R` 规则

转换器不会把 USD 盈亏直接当成 `pnl_R`。必须满足二选一：

```bash
# 方式 A：提供固定 1R 金额
--risk-usd 100

# 方式 B：TradingView CSV 中已有 R 倍数字段
--pnl-r-column "R Multiple"
```

输出文件会同时生成一份审计报告：

```text
data/tradingview_converted_conversion_report.md
```

转换后的原始 CSV 不建议直接作为最终评分输入。推荐先进入 label quality 流程，生成 `outputs/data_quality/cleaned_trades.csv` 后再评分。

## 输出文件

| 文件 | 说明 |
|------|------|
| `outputs/performance_matrix.csv` | Regime 表现矩阵（14 项核心指标 + Edge Concentration） |
| `outputs/monte_carlo_results.csv` | Monte Carlo 风险验证（10 项 MC 指标） |
| `outputs/enable_score.csv` | 策略开启分数（4 子分数 + 4 惩罚乘数 + 解释字段） |
| `outputs/summary_report.md` | Markdown 汇总报告（含风险分类诊断） |

## 评分机制

### Base Score（权重 0.40/0.15/0.25/0.20）
- **Regime Edge Score** — 长期统计 edge（trade_count, win_rate, PF, expectancy, drawdown）
- **Recent Health Score** — 近期健康度（降权不影响 hard-ban）
- **Monte Carlo Stability Score** — 路径风险模拟
- **Risk Control Score** — 风险管理（drawdown, 连亏, avg_loss, payoff）

### 惩罚乘数
- **Sample Confidence Multiplier** — 低样本降权（< min_trades → max(0.50, n/min_trades)）
- **Recent Loss Penalty** — 连亏 ≥3 笔起罚（0.92/0.85/0.75）
- **MC Tail Risk Penalty** — 尾部回撤概率 ≥15% 起罚
- **Edge Concentration Penalty** — 收益过度集中降权

### 状态分级

| 分数 | 状态 |
|------|------|
| 80–100 | 强开启 |
| 65–80 | 中等开启 |
| 50–65 | 弱开启 |
| <50 | 禁用 |

## 常见 Warning

| Warning | 含义 | 处理 |
|---------|------|------|
| `low_sample_size` | trade_count < min_trades | 收集更多数据 |
| `edge_concentration` | 少数交易贡献大部分盈利 | 检查是否依赖极端行情 |
| `high_mc_tail_drawdown` | 模拟路径中高概率大幅回撤 | 降低仓位或增加风控 |
| `recent_losing_streak` | 当前连亏 | 观察是否市场环境变化 |
| `profit_factor_capped` | PF 超过上限被截断 | 检查是否无亏损交易 |
| `payoff_ratio_capped` | Payoff 超过上限被截断 | 检查 avg_loss 是否极小 |
| `review_required` | 需要人工复核 | 阅读 risk_notes 确认结论 |

## 配置文件

`config.yaml` 控制所有权重、阈值、cap、MC 参数、过滤条件。

### 关键配置项

```yaml
min_trades: 30           # 最低样本量
recent_trade_window: 20  # 近期窗口大小
monte_carlo.iterations: 5000  # MC 迭代次数
monte_carlo.method: bootstrap  # 或 shuffle
score_thresholds.strong_enable: 80
metric_caps.max_profit_factor: 10.0
edge_concentration.largest_win_warning_threshold: 0.35
```

## Partial Context Report (P2-14)

只读上下文报告，展示每个 strategy/regime 组合的外部市场环境标签分布（OI、Funding、ETF flow、Session 等）。

> ⚠️ **INFORMATIONAL ONLY** — 不改变 Enable Score / status / 评分逻辑。仅用于人工复盘。

### 运行

```bash
PYTHONPATH=src python3 -m strategy_enable_system.context_report \
  --config config.yaml \
  --input outputs/data_quality/enriched_trades_full_year.csv \
  --quality-summary outputs/data_quality_full_year/label_quality_summary.csv \
  --output-dir outputs/context
```

### 输入

- `outputs/data_quality/enriched_trades_full_year.csv`（P2-12 生成）
- `outputs/data_quality_full_year/label_quality_summary.csv`（P2-12 生成）

### 输出

| 文件 | 说明 |
|------|------|
| `outputs/context/partial_context_summary.csv` | 结构化 summary |
| `outputs/context/partial_context_report.md` | Markdown 报告 |

### Included / Excluded Fields

| 状态 | 字段 |
|------|------|
| ✅ Included | session, structure_state, volatility_state, oi_state, funding_state, etf_flow_state |
| ❌ Excluded | orderflow_state (86% unknown), macro_state (fallback), coinbase_premium_state (无数据) |

### 限制

- 不改变 config.yaml input_path
- 不改变 Enable Score / status / scoring
- 不作为策略开闭依据

## Data Quality Monitor (P2-15)

持续数据质量监控工具，汇总 label_quality、enrichment audit、CoinGlass fetch coverage、partial context readiness、baseline stability，生成统一的监控报告。

### 运行

```bash
PYTHONPATH=src python3 -m strategy_enable_system.data_quality_monitor \
  --config config.yaml \
  --output-dir outputs/monitor
```

### 输入

| 文件 | 说明 |
|------|------|
| `outputs/data_quality_full_year/label_quality_summary.csv` | Label quality summary |
| `outputs/data_quality/enrichment_audit_report_full_year.md` | Enrichment audit |
| `outputs/coinglass_live_full/full_year_fetch_report.md` | CoinGlass fetch report |
| `outputs/context/partial_context_summary.csv` | Partial context summary |
| `outputs/baseline_cleaned_official/` | Official baseline |

### 输出

| 文件 | 说明 |
|------|------|
| `outputs/monitor/data_quality_monitor_summary.csv` | 结构化监控数据 |
| `outputs/monitor/data_quality_monitor_report.md` | Markdown 监控报告 |

### Feature Gates

| Feature | Status | 说明 |
|---------|--------|------|
| Automatic Regime Classifier | BLOCK | orderflow 覆盖不足 |
| Full Market Opportunity Score | BLOCK | 依赖 orderflow + calendar |
| Partial Context Report | PASS | Included fields READY |
| Data Quality Monitor | PASS | 本工具 |

> ⚠️ Monitor 不改变 config.yaml input_path / Enable Score / status。

## 项目结构

```
SSS-Strategy-Score-System/
  config.yaml
  data/sample_trades.csv
  src/strategy_enable_system/
    main.py           # CLI 入口
    config.py         # 配置加载与校验
    data_loader.py    # CSV 读取与数据标准化
    metrics.py        # Regime Performance Matrix + Edge Concentration
    monte_carlo.py    # Bootstrap/Shuffle Monte Carlo 模拟
    scoring.py        # Strategy Enable Score 计算
    reporting.py      # CSV + Markdown 报告生成
    context_report.py # Partial Context Report (P2-14)
    schemas.py        # 字段定义
    utils.py          # 工具函数（Gini, drawdown, 连亏等）
  tests/
  outputs/
```

## 版本

v1.1.0 Stable — P0 + P1 + P2-1 至 P2-20 完成。Market Opportunity Score / Classifier 为 BLOCK（orderflow 覆盖不足）。

## 推荐日常运行

### 默认输入

```yaml
config.yaml → input_path: "outputs/data_quality/cleaned_trades.csv"
```

不使用 `enriched_trades_full_year.csv` 作为默认评分输入。

### 工作流

```bash
# A. 运行默认评分（必选）
PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml

# B. 运行 Data Quality Monitor（推荐）
PYTHONPATH=src python3 -m strategy_enable_system.data_quality_monitor --config config.yaml --output-dir outputs/monitor

# C. 查看报告
#   - outputs/summary_report.md              ← 评分汇总（先看这个）
#   - outputs/monitor/data_quality_monitor_report.md  ← 系统健康

# D. 可选：生成 Partial Context Report（辅助复盘）
PYTHONPATH=src python3 -m strategy_enable_system.context_report --config config.yaml \
  --input outputs/data_quality/enriched_trades_full_year.csv \
  --quality-summary outputs/data_quality_full_year/label_quality_summary.csv \
  --output-dir outputs/context
```

## 不可用功能

| 功能 | 状态 | 原因 |
|------|------|------|
| Automatic Regime Classifier | 🔴 BLOCK | orderflow 14% < 80% |
| Full Market Opportunity Score | 🔴 BLOCK | orderflow + calendar unavailable |

**不要用不完整 orderflow 数据做自动决策。** Partial Context Report 标注为 INFORMATIONAL ONLY。

## 文档入口

| 文档 | 路径 |
|------|------|
| Stable Release Note | `docs/v1_1_stable_release_note.md` |
| User Acceptance Review | `docs/user_acceptance_review_v1_1.md` |
| Partial Feature Readiness | `docs/partial_feature_readiness_review.md` |
| Orderflow Source Decision | `docs/orderflow_source_decision_record.md` |
| Orderflow Data Source Plan | `docs/orderflow_data_source_plan.md` |
| RC Validation Report | `outputs/release_candidate/RC_VALIDATION_REPORT.md` |
| Stable Freeze Checklist | `outputs/release_candidate/STABLE_FREEZE_CHECKLIST.md` |
| Changelog | `CHANGELOG.md` |
