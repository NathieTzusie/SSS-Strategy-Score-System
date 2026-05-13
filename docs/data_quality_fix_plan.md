# Data Quality Fix Plan — Strategy Enable Score System v1.1

**创建时间：** 2026-05-13  
**基于：** `outputs/real_data_validation_report.md`  
**状态：** 计划文档，不涉及代码或数据修改

---

## 1. 当前数据质量问题摘要

基于 `data/combined_trade_log_20260513.csv`（516 笔交易，4 策略 × 3 regime）的运行结果：

| # | 字段 | 问题 | 影响 |
|---|------|------|------|
| Q1 | `session` | 100% `unknown` | `session_distribution` 在 performance matrix 中无意义 |
| Q2 | `structure_state` | 100% `unknown` | P1-2 分层分布章节全部显示 `unknown (516, 100%)` |
| Q3 | `volatility_state` | 100% `unknown` | 同上，且此字段同时属于 status 和 layered 两个 schema |
| Q4 | `orderflow_state` | 100% `unknown` | P1-2 分层分布章节无实际信息 |
| Q5 | `macro_state` | 100% `unknown` | P1-2 分层分布章节无实际信息 |
| Q6 | `oi_state` | 100% `unknown` | 状态字段无信息 |
| Q7 | `cvd_state` | 100% `unknown` | 同上 |
| Q8 | `funding_state` | 100% `unknown` | 同上 |
| Q9 | `coinbase_premium_state` | 100% `unknown` | 同上 |
| Q10 | `etf_flow_state` | 100% `unknown` | 同上 |
| Q11 | `regime_snapshot_id` | **499 个唯一值 / 516 笔交易** | 极度碎片化，几乎每笔一个 snapshot；P1-1 分布章节冗长且无分组意义 |

**核心问题：** 上游数据管道已为每笔交易写入 `trade_id`、`pnl_R`、`regime` 等核心字段，但市场和状态上下文字段全部留空。`regime_snapshot_id` 每笔交易一个唯一时间戳，失去"快照分组"的设计意图。

---

## 2. 优先修复字段（按影响排序）

| 优先级 | 字段 | 理由 |
|--------|------|------|
| **P0** | `regime_snapshot_id` | 当前 499 个唯一值导致 P1-1 分布报告不可读；修复后可展示有意义的市场快照分组 |
| **P0** | `session` | 516 笔全部 unknown，`session_distribution` 完全无信息 |
| **P1** | `structure_state` | 分层 regime 的核心维度，直接影响 P1-2 报告质量 |
| **P1** | `volatility_state` | 关键市场状态，且同时属于 status 和 layered schema |
| **P1** | `orderflow_state` | 分层 regime 维度，区分 spot-led / futures-led |
| **P2** | `macro_state` | 分层 regime 维度，区分 ETF 流入/流出/事件风险 |
| **P2** | `oi_state`, `cvd_state`, `funding_state` | 状态字段，未来可用于 Market Opportunity Score |
| **P2** | `coinbase_premium_state`, `etf_flow_state` | 状态字段，未来可用于 Market Opportunity Score |

---

## 3. `regime_snapshot_id` 命名规范

### 3.1 设计意图

`regime_snapshot_id` 的目标是：**将同一市场状态下发生的多笔交易归入同一个快照**，以便在报告中展示不同市场快照下的策略表现分布。

### 3.2 当前问题

```
当前格式（碎片化）：
  trend_up_uu_2025052917    ← 每笔交易一个唯一 ID
  range_dd_2025062409
  range_dd_2025062514
  ...
  499 个唯一值

期望格式（按天/按 session 聚合）：
  trend_up_20250529        ← 同一天/同一 session 的多笔交易共享同一个 snapshot
  range_20250624
  range_20250625
```

### 3.3 建议命名规则

```
{regime}_{date}
```

示例：

| 当前值 | 建议值 | 说明 |
|--------|--------|------|
| `range_uu_2025050113` | `range_20250501` | 去掉 `uu` 占位和小时，按天聚合 |
| `trend_down_dd_2025111101` | `trend_down_20251111` | 同上 |
| `trend_up_uu_2025100600` | `trend_up_20251006` | 同上 |

规则：
- 格式：`{regime_lowercase}_{YYYYMMDD}`
- regime 使用英文小写，与 `regime` 字段值一致
- 日期基于 `entry_time` 的日期部分
- 同一 (regime, date) 的所有交易共享同一个 `regime_snapshot_id`
- 如果一天内交易过多导致 snapshot 仍然碎片化，可进一步聚合到 `{regime}_{YYYYMM}`（月级别）

### 3.4 替代方案（如果按天仍然碎片化）

```python
# 方案 A：按周聚合
regime_snapshot_id = f"{regime}_W{entry_time.isocalendar().week}_{entry_time.year}"

# 方案 B：按 regime + session 聚合（需先修复 session 字段）
regime_snapshot_id = f"{regime}_{session}_{entry_time.strftime('%Y%m%d')}"
```

---

## 4. 分层 Regime 字段填写规范

### 4.1 `structure_state`

| 值 | 含义 | 何时使用 |
|----|------|---------|
| `trend_up` | 上升趋势 | 价格持续创新高，EMA 多头排列 |
| `trend_down` | 下降趋势 | 价格持续创新低，EMA 空头排列 |
| `range` | 震荡区间 | 价格在明确区间内波动，无方向 |
| `chop` | 无序震荡 | 价格随机波动，无明确区间 |
| `expansion` | 扩张 | 波动率快速扩大，突破区间 |

**回填策略：** 如果已有 `regime` 字段取值为 `trend_up` / `trend_down` / `range`，可以直接复制到 `structure_state`。如果没有其他信息，`structure_state = regime` 是一个合理的起点。

### 4.2 `volatility_state`

| 值 | 含义 | 何时使用 |
|----|------|---------|
| `low` | 低波动 | ATR 或 BBW 低于近期中位数 |
| `medium` | 中等波动 | ATR/BBW 在正常范围 |
| `high` | 高波动 | ATR 或 BBW 显著高于近期中位数 |

**回填策略（第一版）：** 计算每笔交易入场时的 ATR(14) 相对其过去 20 期的百分位：
```python
if atr_percentile < 0.33:  volatility_state = "low"
elif atr_percentile < 0.67: volatility_state = "medium"
else: volatility_state = "high"
```
> 如果无法获取入场时的 ATR 数据，第一版可暂填 `unknown`。

### 4.3 `orderflow_state`

| 值 | 含义 | 何时使用 |
|----|------|---------|
| `spot_led` | 现货驱动 | Coinbase Premium 为正 + 现货成交量占比 > 期货 |
| `futures_led` | 期货驱动 | Open Interest 快速变化 + 期货成交量占主导 |
| `absorption` | 吸收 | 大量成交量但价格不移动（吸筹/派发） |
| `neutral` | 无明确偏向 | 无法判断驱动方 |

**回填策略（第一版）：** 需要 Coinbase Premium Index 和 OI 数据。如果无法获取，第一版可暂填 `unknown`。

### 4.4 `macro_state`

| 值 | 含义 | 何时使用 |
|----|------|---------|
| `ETF_inflow` | ETF 净流入 | 当日或近期 ETF 净流入 |
| `ETF_outflow` | ETF 净流出 | 当日或近期 ETF 净流出 |
| `event_risk` | 事件风险 | 重大经济数据发布日、FOMC 等 |
| `neutral` | 无特殊宏观 | 非事件日，ETF 流量正常 |

**回填策略（第一版）：** 需要 ETF 流量数据和经济日历。如果无法获取，第一版可暂填 `unknown`。

---

## 5. `session` 字段填写规范

### 5.1 标准值

| 值 | 时区 | 覆盖时间 (UTC) | 说明 |
|----|------|---------------|------|
| `Asia` | UTC+8 | 00:00–09:00 | 亚洲交易时段 |
| `London` | UTC+1 | 07:00–16:00 | 伦敦交易时段 |
| `NY` | UTC-5 | 12:00–21:00 | 纽约交易时段 |
| `overlap` | — | 12:00–16:00 | London + NY 重叠 |
| `weekend` | — | 周五 21:00–周日 22:00 | 低流动性时段 |

### 5.2 回填策略（从 `entry_time` 计算）

```python
def classify_session(entry_time_utc):
    hour = entry_time_utc.hour
    weekday = entry_time_utc.weekday()
    
    if weekday >= 5:  # Saturday/Sunday
        return "weekend"
    
    if 0 <= hour < 7:
        return "Asia"
    elif 7 <= hour < 12:
        return "London"
    elif 12 <= hour < 16:
        return "overlap"
    elif 16 <= hour < 21:
        return "NY"
    else:
        return "Asia"  # late evening = early Asia
```

**这是最容易回填的字段**——只需 `entry_time` 即可。建议作为第一个修复项。

---

## 6. 从现有字段回填可用标签（最小可行方案）

### 6.1 可以立即回填的字段（无需额外数据源）

| 字段 | 回填来源 | 方法 |
|------|---------|------|
| `session` | `entry_time` | 按 UTC 小时分类（见 §5.2） |
| `structure_state` | `regime` | 直接复制（trend_up→trend_up, trend_down→trend_down, range→range） |
| `regime_snapshot_id` | `regime` + `entry_time` | 按天聚合（见 §3.3） |

**预计效果：**
- `session` 从 100% unknown → 有 Asia/London/NY/overlap 分布
- `structure_state` 从 100% unknown → 与 regime 一致
- `regime_snapshot_id` 从 499 个唯一值 → ~200 个按天快照（按 regime 分组后每 regime ~70-90 天）

### 6.2 需要外部数据源的字段

| 字段 | 需要的数据 | 建议数据源 |
|------|-----------|-----------|
| `volatility_state` | 入场时 ATR(14) 百分位 | 从 OHLCV 数据计算（已有 5m/30m/1H parquet 数据） |
| `orderflow_state` | Coinbase Premium Index + OI | SisieAssistant 的 CBP/OI 数据 |
| `macro_state` | ETF Flow + 经济日历 | ETF 流量 API + 经济日历 API |
| `oi_state`, `cvd_state`, `funding_state` | OI / CVD / Funding Rate | Coinglass API |
| `coinbase_premium_state` | Coinbase Premium Index | SisieAssistant CBP 数据 |
| `etf_flow_state` | ETF 净流量 | ETF 流量 API |

### 6.3 回填执行顺序

```text
第 1 批（零外部依赖，立即可做）：
  1. session          ← entry_time
  2. structure_state  ← regime
  3. regime_snapshot_id ← regime + entry_time (按天)

第 2 批（需要已有本地数据）：
  4. volatility_state ← 从 OHLCV parquet 计算 ATR 百分位

第 3 批（需要外部 API）：
  5. orderflow_state  ← CBP + OI
  6. macro_state      ← ETF flow + 经济日历
  7. status 字段       ← Coinglass API
```

---

## 7. 修复后验收标准

### 7.1 字段填充率目标

| 字段 | 当前填充率 | 目标填充率 | 验证方式 |
|------|-----------|-----------|---------|
| `session` | 0% (516/516 unknown) | **≥ 95%** | `python3 -c "import pandas as pd; df=pd.read_csv('data/xxx.csv'); print(df['session'].value_counts())"` |
| `structure_state` | 0% | **≥ 95%** | 同上 |
| `regime_snapshot_id` | 100%（但碎片化） | **唯一值 ≤ 200** | 统计 `regime_snapshot_id` 的 `nunique()` |
| `volatility_state` | 0% | **≥ 80%** | 同上 |
| 其他状态字段 | 0% | P2 不强制 | — |

### 7.2 报告质量检查

- [ ] `summary_report.md` → "Market State Snapshot 分布" 章节不再每笔一个 snapshot
- [ ] `summary_report.md` → "分层 Regime 字段分布" 章节中 `structure_state` 不再 100% unknown
- [ ] `performance_matrix.csv` → `session_distribution` 列有意义的分组
- [ ] 运行 `real_data_validation_checklist.md` 第 2 步（regime 标签质量）通过

### 7.3 评分一致性检查

- [ ] 回填前后 `enable_score` 不变（标签回填不影响评分，仅影响报告展示）
- [ ] 回填前后 `status` 分类不变
- [ ] 回填前后 `penalty_drivers` 不变

---

## 8. 不建议修改评分参数的原因

当前 `config.yaml` 的所有参数在真实数据上表现合理：

| 参数 | 当前值 | 不建议修改的原因 |
|------|--------|-----------------|
| `min_trades=30` | 30 | 大部分 ETH 策略 >30 笔；BTP_BTC_1H 数据不足是事实，降低标准会掩盖真实风险 |
| `drawdown_threshold_R=10` | 10 | 有效识别 BAW_ETH_5m 的结构性 MC 尾部风险（82-86%），非阈值 artifact |
| `score_thresholds` | 80/65/50 | 分布合理（0/3/3/6），无堆积或异常偏态 |
| `edge_concentration.*_threshold` | 0.35/0.60/0.70 | 4 个触发均为小样本导致，非阈值问题；数据充足后应自然消失 |
| `metric_caps` | 10.0 | 无组合触发 cap，说明无极端 PF/Payoff 需要截断 |

**核心原则：** 真实数据暴露的是**数据质量问题**（标签缺失、snapshot 碎片化），而非评分算法问题。修复数据质量后，评分结果会更可信，但评分逻辑本身无需调整。

---

## 9. 附录：回填脚本伪代码

```python
# 第 1 批回填：session + structure_state + regime_snapshot_id
import pandas as pd

df = pd.read_csv("data/combined_trade_log_20260513.csv")
df["entry_time"] = pd.to_datetime(df["entry_time"])

# Session
def classify_session(dt):
    h = dt.hour
    w = dt.weekday()
    if w >= 5: return "weekend"
    if 0 <= h < 7: return "Asia"
    if 7 <= h < 12: return "London"
    if 12 <= h < 16: return "overlap"
    if 16 <= h < 21: return "NY"
    return "Asia"

df["session"] = df["entry_time"].apply(classify_session)

# structure_state ← regime
df["structure_state"] = df["regime"]

# regime_snapshot_id ← regime + date
df["regime_snapshot_id"] = (
    df["regime"] + "_" + df["entry_time"].dt.strftime("%Y%m%d")
)

df.to_csv("data/combined_trade_log_20260513_fixed.csv", index=False)
```

---

*Document version 1.0 — for discussion before implementation*
