# Partial Context Report

**生成时间：** 2026-05-14 17:50 
**模式：** `partial_context_mode`

> ⚠️ **INFORMATIONAL ONLY** — 本报告不改变 Enable Score / status / 评分逻辑。
> 本报告仅用于辅助人工复盘，不作为交易决策依据。

## Executive Summary

- **输入文件：** `outputs/data_quality/enriched_trades_full_year.csv`
- **输出目录：** `outputs/context`
- **分组维度：** strategy_name, regime
- **分组数：** 12
- **Included fields：** session, structure_state, volatility_state, oi_state, funding_state, etf_flow_state
- **Excluded fields：** orderflow_state, macro_state, coinbase_premium_state
- **Informational only：** True

## Why Partial Context Only

- **Automatic Regime Classifier：** 仍 BLOCK（orderflow_state 86% unknown）
- **Full Market Opportunity Score：** 仍 BLOCK（依赖 orderflow + calendar）
- **orderflow_state：** Hobbyist taker 4h limit=365 → 仅 60 天覆盖
- **macro_state：** 32.8% fallback neutral，非真实 macro event coverage
- **当前只适合人工复盘上下文，不适合自动决策**

## Field Readiness Overview

| Field | Coverage Rate | Readiness | Reason |
|-------|--------------|-----------|--------|
| session | 100.0% | **PASS** | Built-in UTC-hour rules, always available. |
| structure_state | 100.0% | **PASS** | Derived from regime field, always available. |
| volatility_state | 100.0% | **PASS** | From original trade log, always available. |
| oi_state | 98.0% | **PASS** | CoinGlass OI 1d × 365, 97.3% coverage. |
| funding_state | 98.1% | **PASS** | CoinGlass Funding 1d × 365, 97.5% coverage. |
| etf_flow_state | 100.0% | **PASS** | CoinGlass ETF daily, 100% coverage (BTC 2024+, ETH 2024-07+). |

## Strategy / Regime Context Summary

### ATR_ETH_3m / range

- **总交易数：** 75

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **overlap** | 50.7% | 100.0% | **PASS** |
| structure_state | **range** | 100.0% | 100.0% | **PASS** |
| volatility_state | **medium** | 40.0% | 100.0% | **PASS** |
| oi_state | **flat** | 68.0% | 100.0% | **PASS** |
| funding_state | **positive** | 84.0% | 100.0% | **PASS** |
| etf_flow_state | **neutral** | 37.3% | 100.0% | **PASS** |
  - **session** 分布: overlap: 38, weekend: 19, Asia: 11, London: 5, NY: 2
  - **structure_state** 分布: range: 75
  - **volatility_state** 分布: medium: 30, low: 29, high: 16
  - **oi_state** 分布: flat: 51, rising: 16, falling: 8
  - **funding_state** 分布: positive: 63, negative: 12
  - **etf_flow_state** 分布: neutral: 28, outflow: 26, inflow: 21

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### ATR_ETH_3m / trend_down

- **总交易数：** 36

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **overlap** | 47.2% | 100.0% | **PASS** |
| structure_state | **trend_down** | 100.0% | 100.0% | **PASS** |
| volatility_state | **low** | 47.2% | 100.0% | **PASS** |
| oi_state | **flat** | 61.1% | 100.0% | **PASS** |
| funding_state | **positive** | 69.4% | 100.0% | **PASS** |
| etf_flow_state | **neutral** | 47.2% | 100.0% | **PASS** |
  - **session** 分布: overlap: 17, weekend: 8, Asia: 6, NY: 4, London: 1
  - **structure_state** 分布: trend_down: 36
  - **volatility_state** 分布: low: 17, high: 14, medium: 5
  - **oi_state** 分布: flat: 22, falling: 11, rising: 3
  - **funding_state** 分布: positive: 25, negative: 10, neutral: 1
  - **etf_flow_state** 分布: neutral: 17, outflow: 15, inflow: 4

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### ATR_ETH_3m / trend_up

- **总交易数：** 33

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **overlap** | 45.5% | 100.0% | **PASS** |
| structure_state | **trend_up** | 100.0% | 100.0% | **PASS** |
| volatility_state | **high** | 51.5% | 100.0% | **PASS** |
| oi_state | **flat** | 51.5% | 90.9% | **PASS** |
| funding_state | **positive** | 90.9% | 90.9% | **PASS** |
| etf_flow_state | **inflow** | 54.5% | 100.0% | **PASS** |
  - **session** 分布: overlap: 15, weekend: 9, London: 4, Asia: 4, NY: 1
  - **structure_state** 分布: trend_up: 33
  - **volatility_state** 分布: high: 17, medium: 10, low: 6
  - **oi_state** 分布: flat: 17, rising: 9, falling: 4
  - **funding_state** 分布: positive: 30
  - **etf_flow_state** 分布: inflow: 18, neutral: 10, outflow: 5

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BAW_ETH_5m / range

- **总交易数：** 80

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **overlap** | 26.2% | 100.0% | **PASS** |
| structure_state | **range** | 100.0% | 100.0% | **PASS** |
| volatility_state | **medium** | 33.8% | 100.0% | **PASS** |
| oi_state | **flat** | 56.2% | 96.2% | **PASS** |
| funding_state | **positive** | 76.2% | 96.2% | **PASS** |
| etf_flow_state | **neutral** | 41.2% | 100.0% | **PASS** |
  - **session** 分布: overlap: 21, Asia: 19, NY: 17, London: 12, weekend: 11
  - **structure_state** 分布: range: 80
  - **volatility_state** 分布: medium: 27, low: 27, high: 26
  - **oi_state** 分布: flat: 45, rising: 19, falling: 13
  - **funding_state** 分布: positive: 61, negative: 16
  - **etf_flow_state** 分布: neutral: 33, outflow: 24, inflow: 23

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BAW_ETH_5m / trend_down

- **总交易数：** 56

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **Asia** | 28.6% | 100.0% | **PASS** |
| structure_state | **trend_down** | 100.0% | 100.0% | **PASS** |
| volatility_state | **low** | 42.9% | 100.0% | **PASS** |
| oi_state | **flat** | 53.6% | 100.0% | **PASS** |
| funding_state | **positive** | 67.9% | 100.0% | **PASS** |
| etf_flow_state | **outflow** | 44.6% | 100.0% | **PASS** |
  - **session** 分布: Asia: 16, overlap: 15, weekend: 14, NY: 6, London: 5
  - **structure_state** 分布: trend_down: 56
  - **volatility_state** 分布: low: 24, high: 17, medium: 15
  - **oi_state** 分布: flat: 30, falling: 14, rising: 12
  - **funding_state** 分布: positive: 38, negative: 17, neutral: 1
  - **etf_flow_state** 分布: outflow: 25, neutral: 20, inflow: 11

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BAW_ETH_5m / trend_up

- **总交易数：** 69

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **Asia** | 29.0% | 100.0% | **PASS** |
| structure_state | **trend_up** | 100.0% | 100.0% | **PASS** |
| volatility_state | **high** | 50.7% | 100.0% | **PASS** |
| oi_state | **flat** | 53.6% | 88.4% | **PASS** |
| funding_state | **positive** | 85.5% | 89.9% | **PASS** |
| etf_flow_state | **inflow** | 71.0% | 100.0% | **PASS** |
  - **session** 分布: Asia: 20, weekend: 20, NY: 12, overlap: 11, London: 6
  - **structure_state** 分布: trend_up: 69
  - **volatility_state** 分布: high: 35, low: 21, medium: 13
  - **oi_state** 分布: flat: 37, rising: 13, falling: 11
  - **funding_state** 分布: positive: 59, negative: 3
  - **etf_flow_state** 分布: inflow: 49, neutral: 17, outflow: 3

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BTP_BTC_1H / range

- **总交易数：** 20

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **Asia** | 25.0% | 100.0% | **PASS** |
| structure_state | **range** | 100.0% | 100.0% | **PASS** |
| volatility_state | **high** | 50.0% | 100.0% | **PASS** |
| oi_state | **flat** | 65.0% | 100.0% | **PASS** |
| funding_state | **positive** | 85.0% | 100.0% | **PASS** |
| etf_flow_state | **outflow** | 50.0% | 100.0% | **PASS** |
  - **session** 分布: Asia: 5, London: 4, overlap: 4, NY: 4, weekend: 3
  - **structure_state** 分布: range: 20
  - **volatility_state** 分布: high: 10, medium: 6, low: 4
  - **oi_state** 分布: flat: 13, rising: 4, falling: 3
  - **funding_state** 分布: positive: 17, negative: 3
  - **etf_flow_state** 分布: outflow: 10, inflow: 9, neutral: 1

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BTP_BTC_1H / trend_down

- **总交易数：** 18

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **NY** | 38.9% | 100.0% | **PASS** |
| structure_state | **trend_down** | 100.0% | 100.0% | **PASS** |
| volatility_state | **low** | 44.4% | 100.0% | **PASS** |
| oi_state | **flat** | 77.8% | 100.0% | **PASS** |
| funding_state | **positive** | 72.2% | 100.0% | **PASS** |
| etf_flow_state | **outflow** | 50.0% | 100.0% | **PASS** |
  - **session** 分布: NY: 7, weekend: 4, London: 4, Asia: 2, overlap: 1
  - **structure_state** 分布: trend_down: 18
  - **volatility_state** 分布: low: 8, high: 6, medium: 4
  - **oi_state** 分布: flat: 14, rising: 3, falling: 1
  - **funding_state** 分布: positive: 13, negative: 5
  - **etf_flow_state** 分布: outflow: 9, neutral: 5, inflow: 4

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BTP_BTC_1H / trend_up

- **总交易数：** 7

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **weekend** | 28.6% | 100.0% | **PASS** |
| structure_state | **trend_up** | 100.0% | 100.0% | **PASS** |
| volatility_state | **high** | 57.1% | 100.0% | **PASS** |
| oi_state | **flat** | 57.1% | 100.0% | **PASS** |
| funding_state | **positive** | 71.4% | 100.0% | **PASS** |
| etf_flow_state | **inflow** | 57.1% | 100.0% | **PASS** |
  - **session** 分布: weekend: 2, Asia: 2, overlap: 1, London: 1, NY: 1
  - **structure_state** 分布: trend_up: 7
  - **volatility_state** 分布: high: 4, low: 2, medium: 1
  - **oi_state** 分布: flat: 4, falling: 3
  - **funding_state** 分布: positive: 5, neutral: 1, negative: 1
  - **etf_flow_state** 分布: inflow: 4, outflow: 2, neutral: 1

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BTP_ETH_30m / range

- **总交易数：** 49

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **weekend** | 28.6% | 100.0% | **PASS** |
| structure_state | **range** | 100.0% | 100.0% | **PASS** |
| volatility_state | **low** | 46.9% | 100.0% | **PASS** |
| oi_state | **flat** | 73.5% | 100.0% | **PASS** |
| funding_state | **positive** | 81.6% | 100.0% | **PASS** |
| etf_flow_state | **neutral** | 36.7% | 100.0% | **PASS** |
  - **session** 分布: weekend: 14, Asia: 11, overlap: 11, London: 7, NY: 6
  - **structure_state** 分布: range: 49
  - **volatility_state** 分布: low: 23, high: 13, medium: 13
  - **oi_state** 分布: flat: 36, rising: 8, falling: 5
  - **funding_state** 分布: positive: 40, negative: 9
  - **etf_flow_state** 分布: neutral: 18, inflow: 16, outflow: 15

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BTP_ETH_30m / trend_down

- **总交易数：** 44

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **weekend** | 40.9% | 100.0% | **PASS** |
| structure_state | **trend_down** | 100.0% | 100.0% | **PASS** |
| volatility_state | **low** | 56.8% | 100.0% | **PASS** |
| oi_state | **flat** | 65.9% | 100.0% | **PASS** |
| funding_state | **positive** | 75.0% | 100.0% | **PASS** |
| etf_flow_state | **outflow** | 40.9% | 100.0% | **PASS** |
  - **session** 分布: weekend: 18, NY: 11, London: 6, Asia: 5, overlap: 4
  - **structure_state** 分布: trend_down: 44
  - **volatility_state** 分布: low: 25, high: 12, medium: 7
  - **oi_state** 分布: flat: 29, rising: 13, falling: 2
  - **funding_state** 分布: positive: 33, negative: 11
  - **etf_flow_state** 分布: outflow: 18, neutral: 16, inflow: 10

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

### BTP_ETH_30m / trend_up

- **总交易数：** 29

| Field | Dominant Value | Share | Coverage | Readiness |
|-------|---------------|-------|----------|-----------|
| session | **Asia** | 37.9% | 100.0% | **PASS** |
| structure_state | **trend_up** | 100.0% | 100.0% | **PASS** |
| volatility_state | **high** | 51.7% | 100.0% | **PASS** |
| oi_state | **flat** | 62.1% | 100.0% | **PASS** |
| funding_state | **positive** | 86.2% | 100.0% | **PASS** |
| etf_flow_state | **inflow** | 82.8% | 100.0% | **PASS** |
  - **session** 分布: Asia: 11, London: 6, overlap: 5, weekend: 5, NY: 2
  - **structure_state** 分布: trend_up: 29
  - **volatility_state** 分布: high: 15, medium: 11, low: 3
  - **oi_state** 分布: flat: 18, falling: 8, rising: 3
  - **funding_state** 分布: positive: 25, negative: 4
  - **etf_flow_state** 分布: inflow: 24, neutral: 3, outflow: 2

> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。

## Excluded Fields

以下字段在当前 partial_context_mode 中被排除：

| Field | Reason |
|-------|--------|
| orderflow_state | Readiness BLOCK — CoinGlass Hobbyist taker 4h 仅 60 天覆盖，86% unknown |
| macro_state | 32.8% fallback neutral — 无 financial calendar (401 Hobbyist)，非真实 macro event coverage |
| coinbase_premium_state | No reliable data source configured |

## Usage Guidance

✅ **可以用于：**
- 人工复盘时理解 strategy/regime 的历史外部市场环境
- 辅助判断策略在不同环境下的行为分布
- 作为数据质量报告的补充

❌ **不可用于：**
- 自动开关策略（需 classifier）
- 调整 enable_score 或 status
- 作为 Market Opportunity Score 输入
- 替代人工对环境的判断

## Next Step

**建议：P2-15 Data Quality Monitor 或 Context Report Review**

选择 A — Data Quality Monitor：在现有 label_quality + enrichment audit 基础上开发持续监控
选择 B — Context Report Review：基于本报告做人工 review 后决定下一步
选择 C — Degraded Market Opp Offline Experiment：OI+Funding+ETF 相关性探索（仅 offline）


---

*Generated by Strategy Enable Score System v1.1 — P2-14 Partial Context Report*