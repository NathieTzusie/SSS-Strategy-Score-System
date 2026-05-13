# Strategy Enable Score System v1.1

策略质量评估系统 — 判断已存在策略在当前市场环境下是否应开启（强/中/弱/禁用）。

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

## 项目结构

```
SSS-Strategy-Score-System/
  config.yaml
  data/sample_trades.csv
  src/strategy_enable_system/
    main.py          # CLI 入口
    config.py        # 配置加载与校验
    data_loader.py   # CSV 读取与数据标准化
    metrics.py       # Regime Performance Matrix + Edge Concentration
    monte_carlo.py   # Bootstrap/Shuffle Monte Carlo 模拟
    scoring.py       # Strategy Enable Score 计算
    reporting.py     # CSV + Markdown 报告生成
    schemas.py       # 字段定义
    utils.py         # 工具函数（Gini, drawdown, 连亏等）
  tests/
  outputs/
```

## 版本

v1.1 — P0 + P1 完成。Market Opportunity Score 为 placeholder（默认 1.0）。
