# Strategy Enable Score System v1.1 设计文档

## 1. 项目目标

本项目用于构建一套本地可运行的 Python 量化策略矩阵评估系统。

系统目标不是自动寻找 entry，而是判断：

> 某个已存在策略，在当前市场环境下是否应该强开启、中等开启、弱开启或禁用。

第一版重点是把交易者对“策略适合什么盘面”的经验判断，转化为可计算、可复盘、可扩展的 Strategy Enable Score。

核心输出：

- Regime Performance Matrix
- Monte Carlo 风险验证结果
- Strategy Enable Score
- 策略状态建议
- Markdown 汇总报告

状态分级：

| 分数区间 | 状态 |
|---:|---|
| 80-100 | 强开启 |
| 65-80 | 中等开启 |
| 50-65 | 弱开启 |
| <50 | 禁用 |

设计原则：

- 第一版简单、稳定、可解释
- 不使用复杂机器学习
- 不做完整 Walk-Forward
- 默认使用 `pnl_R`，不以 `pnl_usd` 作为核心统计单位
- 所有权重、阈值、过滤条件必须可配置
- 每个开启或禁用结论必须能解释原因
- 区分“策略失效”和“市场暂时无机会”

## 2. 系统总体架构

### 2.1 数据流

```text
CSV trades
  ↓
Data Loader
  ↓
Standardized Trades DataFrame
  ↓
Regime Performance Matrix
  ├─ Core Performance Metrics
  ├─ Edge Concentration Metrics
  └─ Layered Regime Distribution
  ↓
Monte Carlo Risk Validation
  ↓
Strategy Enable Score
  ↓
Market Opportunity Score Placeholder
  ↓
Final Activation Score
  ↓
CSV outputs + Markdown summary
```

### 2.2 推荐项目结构

```text
strategy_enable_system/
  README.md
  requirements.txt
  config.yaml
  data/
    sample_trades.csv
  outputs/
    performance_matrix.csv
    monte_carlo_results.csv
    enable_score.csv
    summary_report.md
  src/
    strategy_enable_system/
      __init__.py
      main.py
      config.py
      data_loader.py
      metrics.py
      monte_carlo.py
      scoring.py
      reporting.py
      schemas.py
      utils.py
  tests/
    test_data_loader.py
    test_metrics.py
    test_monte_carlo.py
    test_scoring.py
```

### 2.3 模块边界

| 模块 | 职责 |
|---|---|
| `schemas.py` | 管理字段定义、必填字段、可选字段 |
| `config.py` | 读取并校验 `config.yaml` |
| `data_loader.py` | 读取 CSV、校验字段、标准化数据 |
| `metrics.py` | 计算表现矩阵、回撤、连亏、edge concentration |
| `monte_carlo.py` | 对每个 `strategy_name + regime` 组合做风险模拟 |
| `scoring.py` | 计算 Enable Score、Final Activation Score 和解释字段 |
| `reporting.py` | 输出 CSV 和 Markdown summary |
| `main.py` | CLI 入口，串联完整流程 |

## 3. CSV Schema

### 3.1 核心字段

| 字段 | 类型 | 是否必填 | 说明 |
|---|---:|---:|---|
| `trade_id` | string | 是 | 唯一交易 ID |
| `strategy_name` | string | 是 | 策略名称 |
| `symbol` | string | 是 | 交易品种 |
| `direction` | string | 是 | `long` 或 `short` |
| `entry_time` | datetime | 是 | 入场时间 |
| `exit_time` | datetime | 是 | 出场时间 |
| `pnl_R` | float | 是 | R 倍数收益，核心统计单位 |
| `pnl_usd` | float | 否 | 美元盈亏，辅助字段 |
| `session` | string | 是 | 交易时段 |
| `regime` | string | 是 | 第一版主分组字段 |
| `setup_type` | string | 否 | setup 类型 |

### 3.2 状态字段

| 字段 | 类型 | 是否必填 | 说明 |
|---|---:|---:|---|
| `volatility_state` | string | 否 | 波动率状态 |
| `oi_state` | string | 否 | Open Interest 状态 |
| `cvd_state` | string | 否 | CVD 状态 |
| `funding_state` | string | 否 | Funding 状态 |
| `coinbase_premium_state` | string | 否 | Coinbase Premium 状态 |
| `etf_flow_state` | string | 否 | ETF Flow 状态 |

### 3.3 v1.1 新增字段

| 字段 | 类型 | 是否必填 | 用途 |
|---|---:|---:|---|
| `regime_snapshot_id` | string | 否 | 更细粒度市场状态快照 |
| `structure_state` | string | 否 | 结构状态 |
| `orderflow_state` | string | 否 | 订单流状态 |
| `macro_state` | string | 否 | 宏观或事件状态 |

说明：

- `regime` 第一版仍然是主分组字段。
- `regime_snapshot_id` 先作为 Reporting 统计字段，不参与核心评分。
- 分层字段先用于未来扩展，不在 v1 中自动生成 `regime`。
- `volatility_state` 已存在，同时也属于分层 regime 结构的一部分，不需要重复建字段。

### 3.4 分层 regime 示例值

| 字段 | 示例 |
|---|---|
| `structure_state` | `trend_up`, `trend_down`, `range`, `chop`, `reversal`, `expansion`, `compression` |
| `volatility_state` | `low`, `medium`, `high` |
| `orderflow_state` | `spot_led`, `futures_led`, `absorption`, `distribution`, `squeeze`, `neutral` |
| `macro_state` | `ETF_inflow`, `ETF_outflow`, `event_risk`, `neutral` |

### 3.5 缺失值处理

| 字段类型 | 处理规则 |
|---|---|
| 核心字段缺失 | 报错并停止 |
| `regime` 缺失 | 报错并停止 |
| `regime_snapshot_id` 缺失 | 填充为 `unknown` |
| 分层字段缺失 | 填充为 `unknown` |
| 状态字段缺失 | 填充为 `unknown` |
| `pnl_usd` 缺失 | 填充为 `0.0` 并记录 warning |
| `pnl_R` 非数值 | 报错并指出行号 |
| 时间字段无法解析 | 报错并指出行号 |
| `exit_time < entry_time` | 默认报错 |
| 重复 `trade_id` | 默认 warning，可配置为 error |

### 3.6 示例 CSV

```csv
trade_id,strategy_name,symbol,direction,entry_time,exit_time,pnl_R,pnl_usd,session,regime,regime_snapshot_id,structure_state,volatility_state,orderflow_state,macro_state,oi_state,cvd_state,funding_state,coinbase_premium_state,etf_flow_state,setup_type
T001,BTC_OB_Reversal,BTCUSDT,long,2026-01-02 09:15:00,2026-01-02 15:30:00,1.8,360,London,trend_up,trend_up_high_vol_positive_funding,trend_up,high,futures_led,ETF_inflow,rising,bullish,positive,positive,inflow,discount_ob
T002,BTC_OB_Reversal,BTCUSDT,long,2026-01-04 10:00:00,2026-01-04 14:10:00,-1.0,-200,London,trend_up,trend_up_high_vol_positive_funding,trend_up,high,futures_led,ETF_inflow,rising,neutral,positive,positive,inflow,discount_ob
T003,ETH_FVG_Continuation,ETHUSDT,short,2026-01-05 13:20:00,2026-01-05 18:40:00,2.4,480,NY,trend_down,trend_down_high_vol_futures_led,trend_down,high,futures_led,event_risk,rising,bearish,positive,negative,outflow,premium_fvg
T004,BTC_Range_MeanRevert,BTCUSDT,long,2026-01-07 08:30:00,2026-01-07 12:45:00,0.9,180,Asia,range,range_low_vol_spot_absorption,range,low,absorption,neutral,flat,bullish,negative,neutral,neutral,range_sweep
```

## 4. 核心模块设计

## 4.1 Module 1：Data Loader

职责：

- 读取一个或多个 CSV
- 校验必填字段
- 标准化字段名和类型
- 转换 `entry_time`、`exit_time`
- 校验 `pnl_R` 是否为数值
- 支持按 `symbol`、`strategy_name`、日期范围过滤
- 支持 `regime_snapshot_id` 和分层 regime 字段
- 缺失可选状态字段时填充 `unknown`

输入：

- `config.yaml`
- CSV 文件路径列表

输出：

- 标准化 `pandas.DataFrame`

验收标准：

- 缺字段时报出明确字段名
- 类型错误时报出行号
- 过滤后无数据时明确提示
- 即使原始 CSV 缺少可选字段，输出 DataFrame 也必须包含这些字段

## 4.2 Module 2：Regime Performance Matrix

主分组维度：

```text
strategy_name + regime
```

核心指标：

| 指标 | 说明 |
|---|---|
| `trade_count` | 交易数量 |
| `win_rate` | `pnl_R > 0` 的比例 |
| `avg_R` | 平均 R |
| `median_R` | 中位数 R |
| `total_R` | 总 R |
| `profit_factor` | 总盈利 R / 总亏损绝对值 |
| `max_drawdown_R` | 按时间排序权益曲线最大回撤 |
| `expectancy_R` | 第一版等同 `avg_R` |
| `avg_win_R` | 盈利交易平均 R |
| `avg_loss_R` | 亏损交易平均 R |
| `payoff_ratio` | `avg_win_R / abs(avg_loss_R)` |
| `longest_losing_streak` | 最大连续亏损笔数 |
| `session_distribution` | session 占比分布 |
| `low_sample_warning` | `trade_count < min_trades` |

### 4.2.1 Edge Concentration Metrics

目的：

识别策略是否过度依赖少数几笔极端盈利，避免误把长尾偶发收益当成稳定 edge。

新增指标：

| 指标 | 计算方式 |
|---|---|
| `top_5_trade_contribution` | 最大 5 笔盈利 / 总盈利 |
| `top_10_percent_trade_contribution` | 最大 10% 盈利交易贡献 / 总盈利 |
| `largest_win_contribution` | 最大单笔盈利 / 总盈利 |
| `gini_pnl_R` | 使用正收益 `pnl_R > 0` 的贡献计算 Gini |
| `edge_concentration_warning` | 是否触发集中度风险 |

计算规则：

- 只统计 `pnl_R > 0` 的盈利贡献。
- 如果总盈利 `total_positive_R <= 0`，上述贡献指标填充为 `null`，并触发 warning。
- `gini_pnl_R` 第一版使用正收益贡献计算，不使用全部 `pnl_R`。

默认 warning 阈值：

| 条件 | 阈值 |
|---|---:|
| `largest_win_contribution` | > 0.35 |
| `top_5_trade_contribution` | > 0.60 |
| `top_10_percent_trade_contribution` | > 0.70 |

触发提示：

```text
该组合可能依赖少数极端行情，不宜仅凭总收益判断稳定性。
```

### 4.2.2 profit_factor 与 payoff_ratio cap

规则：

- `profit_factor` 必须 cap
- `payoff_ratio` 必须 cap
- cap 值来自 `config.yaml`
- 触发 cap 时写入 warning

设计原因：

- 极高 `profit_factor` 可能来自样本太少或没有亏损交易。
- 极高 `payoff_ratio` 可能来自低胜率长尾策略，不应被误判为稳定策略。

## 4.3 Module 3：Monte Carlo Risk Validation

职责：

对每个 `strategy_name + regime` 组合，使用 `pnl_R` 序列做路径风险模拟。

默认方法：

```text
bootstrap
```

第一版支持：

| 方法 | 说明 |
|---|---|
| `shuffle` | 随机重排原始交易顺序 |
| `bootstrap` | 有放回抽样，长度等于原始交易数量 |

输出指标：

| 指标 | 说明 |
|---|---|
| `median_total_R` | 模拟总收益中位数 |
| `p5_total_R` | 总收益 5 分位 |
| `p95_total_R` | 总收益 95 分位 |
| `median_max_drawdown_R` | 最大回撤中位数 |
| `p95_max_drawdown_R` | 最大回撤 95 分位 |
| `worst_max_drawdown_R` | 最坏路径最大回撤 |
| `median_longest_losing_streak` | 连亏中位数 |
| `p95_longest_losing_streak` | 连亏 95 分位 |
| `probability_of_negative_total_R` | 总收益为负概率 |
| `probability_drawdown_exceeds_threshold` | 回撤超过阈值概率 |

配置要求：

- `iterations` 默认 5000
- `drawdown_threshold_R` 默认 10R
- `random_seed` 可配置
- 固定 seed 后结果必须可复现

## 4.4 Module 4：Strategy Enable Score

### 4.4.1 核心思想

评分系统必须体现：

- `regime` 下长期表现比近期噪声更重要
- 近期恶化只用于降权和提示，不得单独 hard-ban 策略
- Monte Carlo 尾部风险必须纳入
- 低样本、高集中度、高回撤要降权
- 每个分数必须可解释

### 4.4.2 Base Score

```text
Base Enable Score =
  Regime Edge Score * 0.40
+ Recent Health Score * 0.15
+ Monte Carlo Stability Score * 0.25
+ Risk Control Score * 0.20
```

### 4.4.3 Final Enable Score

```text
Enable Score =
  Base Enable Score
  * Sample Confidence Multiplier
  * Recent Loss Penalty
  * MC Tail Risk Penalty
  * Edge Concentration Penalty
```

### 4.4.4 Final Activation Score

```text
Final Activation Score =
  Enable Score * Market Opportunity Score
```

v1 中：

```text
Market Opportunity Score = 1.0
Final Activation Score = Enable Score
```

### 4.4.5 子分数

#### Regime Edge Score

```text
Regime Edge Score =
  trade_count_score * 0.20
+ win_rate_score * 0.20
+ profit_factor_score * 0.25
+ expectancy_score * 0.25
+ drawdown_score * 0.10
```

#### Recent Health Score

```text
Recent Health Score =
  recent_avg_R_score * 0.35
+ recent_win_rate_score * 0.25
+ recent_drawdown_score * 0.25
+ recent_losing_streak_score * 0.15
```

约束：

- Recent Health 不得单独导致策略直接禁用。
- 近期恶化严重时，只写入 `risk_notes`、`penalty_drivers` 和 `review_required`。

#### Monte Carlo Stability Score

```text
Monte Carlo Stability Score =
  negative_total_score * 0.35
+ p95_drawdown_score * 0.35
+ p95_losing_streak_score * 0.20
+ p5_total_score * 0.10
```

#### Risk Control Score

```text
Risk Control Score =
  max_drawdown_score * 0.30
+ losing_streak_score * 0.25
+ avg_loss_score * 0.20
+ payoff_ratio_score * 0.25
```

### 4.4.6 乘数惩罚

#### Sample Confidence Multiplier

```text
if trade_count >= min_trades:
    multiplier = 1.00
else:
    multiplier = max(0.50, trade_count / min_trades)
```

#### Recent Loss Penalty

```text
current_losing_streak >= 5: multiplier = 0.75
current_losing_streak == 4: multiplier = 0.85
current_losing_streak == 3: multiplier = 0.92
else: multiplier = 1.00
```

#### MC Tail Risk Penalty

```text
probability_drawdown_exceeds_threshold >= 0.40: multiplier = 0.75
probability_drawdown_exceeds_threshold >= 0.25: multiplier = 0.85
probability_drawdown_exceeds_threshold >= 0.15: multiplier = 0.92
else: multiplier = 1.00
```

#### Edge Concentration Penalty

```text
if largest_win_contribution > 0.50 and top_5_trade_contribution > 0.75:
    multiplier = 0.85
elif edge_concentration_warning:
    multiplier = 0.90
else:
    multiplier = 1.00
```

## 4.5 Module 5：Reporting

输出文件：

```text
outputs/performance_matrix.csv
outputs/monte_carlo_results.csv
outputs/enable_score.csv
outputs/summary_report.md
```

`summary_report.md` 必须包含：

- 各策略在各 `regime` 下的表现
- 哪些组合可开启
- 哪些组合应禁用
- 样本不足提示
- Monte Carlo 最坏路径风险
- 最近表现是否恶化
- Edge Concentration 风险提示
- `regime_snapshot_id` 分布
- 分层 regime 标签分布
- Market Opportunity Score placeholder 说明

Reporting 中需要明确区分：

- 策略可能失效
- 市场暂时无机会
- 样本不足
- 极端盈利依赖
- Monte Carlo 尾部风险过高

## 5. enable_score.csv 字段

建议输出字段：

```text
strategy_name
regime
enable_score
market_opportunity_score
final_activation_score
status

regime_edge_score
recent_health_score
monte_carlo_stability_score
risk_control_score

sample_confidence_multiplier
recent_loss_penalty
mc_tail_risk_penalty
edge_concentration_penalty

score_drivers
penalty_drivers
primary_reason
risk_notes
review_required
low_sample_warning
edge_concentration_warning
```

`score_drivers` 示例：

```text
positive_expectancy
strong_profit_factor
healthy_mc_distribution
controlled_drawdown
stable_payoff_ratio
```

`penalty_drivers` 示例：

```text
low_sample_size
recent_losing_streak
high_mc_tail_drawdown
edge_concentration
profit_factor_capped
payoff_ratio_capped
```

`review_required = true` 的条件：

- `low_sample_warning == true`
- `edge_concentration_warning == true`
- `probability_drawdown_exceeds_threshold > mc_drawdown_probability_review_threshold`
- `current_losing_streak >= losing_streak_review_threshold`
- `trade_count < min_trades`

## 6. config.yaml 设计

```yaml
input_path:
  - "data/sample_trades.csv"

output_dir: "outputs"

min_trades: 30
recent_trade_window: 20

regime_schema:
  use_layered_regime_fields: true
  fill_missing_layered_fields_with: "unknown"

monte_carlo:
  iterations: 5000
  method: "bootstrap"
  drawdown_threshold_R: 10
  random_seed: 42

market_opportunity:
  enabled: false
  default_score: 1.0

edge_concentration:
  enabled: true
  largest_win_warning_threshold: 0.35
  top_5_warning_threshold: 0.60
  top_10_percent_warning_threshold: 0.70

score_weights:
  regime_edge: 0.40
  recent_health: 0.15
  monte_carlo_stability: 0.25
  risk_control: 0.20

score_thresholds:
  strong_enable: 80
  medium_enable: 65
  weak_enable: 50

metric_caps:
  max_profit_factor: 10.0
  max_payoff_ratio: 10.0

review_rules:
  losing_streak_review_threshold: 4
  mc_drawdown_probability_review_threshold: 0.25
  low_sample_requires_review: true
  edge_concentration_requires_review: true

filters:
  symbol: []
  strategy_name: []
  date_start: null
  date_end: null

validation:
  duplicate_trade_id: "warning"
  require_exit_after_entry: true
  fill_missing_state_with: "unknown"
```

## 7. Time Under Water / Recovery 预留

v1 不强制实现，但需要在 `metrics.py` 中预留函数或 TODO。

目的：

衡量策略资金曲线长期不创新高的痛苦程度。

预留函数：

```python
def calculate_time_under_water(equity_curve):
    """TODO: 计算资金曲线低于前高的持续交易数。"""
    pass


def calculate_max_recovery_trades(equity_curve):
    """TODO: 计算从回撤到重新创新高所需的最大交易数。"""
    pass


def calculate_average_recovery_trades(equity_curve):
    """TODO: 计算平均恢复交易数。"""
    pass
```

## 8. OpenClaw 开发任务

## 8.1 P0 必须做

### Task P0-1：创建项目骨架

目标：

- 建立 Python 项目目录、依赖文件、入口文件。

输入：

- 本设计文档。

输出：

- 项目结构、`README.md`、`requirements.txt`、基础模块文件。

验收标准：

- 可以运行 `python -m strategy_enable_system.main --config config.yaml`。

可能的坑：

- Windows 路径兼容。
- Python 包导入路径错误。

### Task P0-2：实现 Config Loader

目标：

- 读取并校验 `config.yaml`。

输入：

- `config.yaml`。

输出：

- 标准化配置对象。

验收标准：

- 缺少关键配置时报清楚错误。
- 权重总和异常时给 warning 或 error。

可能的坑：

- YAML 空列表、`null`、路径解析。

### Task P0-3：实现 Data Loader

目标：

- 读取 CSV，校验字段，转换类型，应用过滤。

输入：

- CSV 文件、配置。

输出：

- 标准化 DataFrame。

验收标准：

- 支持 `regime_snapshot_id`。
- 支持 `structure_state`、`volatility_state`、`orderflow_state`、`macro_state`。
- 缺失分层字段时填充 `unknown`。
- `pnl_R` 错误、时间错误、核心字段缺失都有清楚提示。

可能的坑：

- 时间格式混乱。
- 重复 `trade_id`。
- 过滤后无数据。

### Task P0-4：实现 Metrics Engine

目标：

- 计算 Regime Performance Matrix 和 Edge Concentration Metrics。

输入：

- 标准化 DataFrame。

输出：

- performance matrix DataFrame。

验收标准：

- 基础指标与手工计算一致。
- `profit_factor` 与 `payoff_ratio` 正确 cap。
- Edge Concentration warning 正确触发。

可能的坑：

- `profit_factor` 除零。
- 最大回撤符号。
- 连亏计算。
- 总盈利小于等于 0 时贡献率处理。

### Task P0-5：实现 Monte Carlo 模块

目标：

- 对每个组合执行 Monte Carlo 风险验证。

输入：

- trades DataFrame、MC 配置。

输出：

- monte_carlo_results DataFrame。

验收标准：

- 固定 seed 下结果可复现。
- 输出所有要求的分位数和概率指标。

可能的坑：

- 回撤计算方向。
- 抽样方式不一致。
- 小样本结果误导。

### Task P0-6：实现 Scoring 模块

目标：

- 计算新版 Enable Score、Market Opportunity placeholder 和解释字段。

输入：

- performance matrix、MC results、recent trades、配置。

输出：

- enable_score DataFrame。

验收标准：

- 使用新权重：`0.40 / 0.15 / 0.25 / 0.20`。
- Recent Health 不得单独 hard-ban 策略。
- 输出 `market_opportunity_score` 和 `final_activation_score`。
- 输出 `score_drivers`、`penalty_drivers`、`review_required`。

可能的坑：

- 分数映射不可解释。
- 惩罚乘数过重。
- 极高 payoff ratio 被误判为稳定。

### Task P0-7：实现 Reporting

目标：

- 输出 CSV 和 Markdown summary。

输入：

- 三个结果 DataFrame。

输出：

- `performance_matrix.csv`
- `monte_carlo_results.csv`
- `enable_score.csv`
- `summary_report.md`

验收标准：

- Markdown 包含开启 / 禁用原因。
- 包含样本不足、MC 尾部风险、近期恶化、edge concentration 提示。
- 说明 Market Opportunity Score 当前为 placeholder。

可能的坑：

- 报告过长。
- 排序不清晰。
- 只给结论不解释原因。

### Task P0-8：编写核心单元测试

目标：

- 覆盖核心计算逻辑。

输入：

- 小型固定测试数据。

输出：

- `pytest` 测试。

验收标准：

- `pytest` 全部通过。
- 覆盖 metrics、scoring、data loader、Monte Carlo seed reproducibility。

可能的坑：

- 浮点误差。
- 随机模拟不可复现。

## 8.2 P1 应该做

- 支持多个 CSV 合并。
- 支持 `shuffle` / `bootstrap` Monte Carlo 切换。
- Reporting 展示 `regime_snapshot_id` 分布。
- Reporting 展示分层 regime 字段分布。
- Reporting 展示 Edge Concentration 详细解释。
- 扩展 `review_required` 规则。
- Summary 中区分策略失效、市场暂时无机会、样本不足、极端盈利依赖。
- 增加 CLI 参数，例如 `--config`。
- 增加 README 与示例数据。

## 8.3 P2 以后做

- 自动 regime classifier。
- Market Opportunity Score 正式实现。
- Time Under Water Metrics。
- Recovery Metrics。
- Block Bootstrap。
- Walk-Forward OOS。
- 图表输出。
- 本地网页 Dashboard。
- 实时策略启停提醒。
- 与交易日志系统联动。

## 9. 开发阶段规划

### Phase 1：可运行骨架

目标：

- 项目能跑通完整 pipeline。

范围：

- 项目结构
- config loader
- data loader
- sample CSV
- CLI 入口

完成标志：

- 输入 sample CSV 后能生成空壳或基础结果文件。

### Phase 2：核心统计与风险验证

目标：

- 让系统具备可信的统计基础。

范围：

- Regime Performance Matrix
- Edge Concentration Metrics
- Monte Carlo Risk Validation
- 核心单元测试

完成标志：

- `performance_matrix.csv` 和 `monte_carlo_results.csv` 指标正确。

### Phase 3：评分系统与解释字段

目标：

- 生成可解释的策略开启分数。

范围：

- Enable Score
- Final Activation Score
- Market Opportunity placeholder
- `score_drivers`
- `penalty_drivers`
- `review_required`

完成标志：

- `enable_score.csv` 能解释每个组合为什么开启或禁用。

### Phase 4：报告与交付体验

目标：

- 让非代码视角也能快速判断策略状态。

范围：

- Markdown summary
- regime_snapshot 分布
- 分层 regime 分布
- 风险提示
- README

完成标志：

- 用户只看 `summary_report.md` 就能知道哪些策略可开启、哪些需要复核、哪些应禁用。

### Phase 5：未来扩展

目标：

- 从离线评估扩展到更强的策略控制系统。

范围：

- Market Opportunity Score
- 自动 regime classifier
- Block Bootstrap
- Walk-Forward OOS
- Dashboard
- 实时提醒

完成标志：

- 系统可以从“历史评估工具”升级为“策略启停决策层”。

## 10. 当前定稿结论

v1.1 当前定稿重点：

- `regime` 继续作为第一版主分组字段。
- `regime_snapshot_id` 用于细粒度市场状态快照，先不参与评分。
- 分层 regime 字段用于未来扩展，不在 v1 中自动生成 regime。
- Edge Concentration Metrics 必须进入 P0，防止少数极端盈利误导评分。
- Recent Health 权重降低到 0.15，避免误判“市场暂时无机会”为“策略失效”。
- Market Opportunity Score 在 v1 中默认 1.0，只做接口预留。
- `enable_score.csv` 必须包含解释字段，确保每个结果可复盘。
- P0 目标是做出稳定、可运行、可测试的本地 Python v1 系统。
