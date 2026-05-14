# P2-12 Full-Year Label Enrichment + Regression Report

**生成时间：** 2026-05-14 14:10 CEST  
**版本：** Strategy Enable Score System v1.1

---

## Executive Summary

| 项目 | 值 |
|------|-----|
| Input cleaned path | `outputs/data_quality/cleaned_trades.csv` |
| Processed dir | `data/external/coinglass_live_full/processed` (P2-11) |
| Enriched output | `outputs/data_quality/enriched_trades_full_year.csv` |
| Pipeline config | `config.enriched.full_year.pipeline.yaml` |
| Pipeline output | `outputs/validation_enriched_full_year/` |
| Pipeline 是否跑通 | ✅ 是（516 trades, 12 组合） |
| 是否修改评分公式 | ❌ 否 |
| 是否修改 config.yaml input_path | ❌ 否（仍为 cleaned_trades.csv） |
| 是否建议设 enriched 为默认输入 | ❌ 暂不建议 |

---

## Enrichment Coverage

### 回填统计（516 笔交易）

| Field | Before Unknown | Filled | Missing Match | After Unknown | Fill Rate | Notes |
|-------|---------------|--------|---------------|---------------|-----------|-------|
| oi_state | 516 (100%) | 502 | 14 | 14 (2.7%) | **97.3%** | ✅ 14 missing = ETH 2025-05-01~14 窗口外 |
| funding_state | 516 (100%) | 503 | 13 | 13 (2.5%) | **97.5%** | ✅ 13 missing = ETH 2025-05-01~14 |
| orderflow_state | 516 (100%) | 72 | 444 | 444 (86.0%) | **14.0%** | ⚠️ Taker 4h 仅覆盖 60 天 |
| etf_flow_state | 516 (100%) | 516 | 0 | 0 (0%) | **100%** | ✅ BTC ETF 2024-01+, ETH ETF 2024-07+ |
| macro_state | 516 (100%) | 516 | 0 | 0 (0%) | **100%** | ✅ ETF flow + fallback "neutral" |

### 限制说明

**Taker / orderflow_state 覆盖受 Hobbyist limit=365 @ 4h = ~60 天限制**
- BTC: 5/45 (11%) 笔交易被回填 orderflow_state
- ETH: 67/471 (14%) 笔交易被回填 orderflow_state
- 这是 CoinGlass Hobbyist plan 的结构性限制，无法通过代码改善

**Financial Calendar 不可用 (401 Hobbyist)**
- `macro_state` = "event_risk" 标签不可用
- 回填方式：ETF flow → "flow_driven"；其他 → "neutral"
- 当前 macro_state 的 PASS 是 fallback 结果，**不等同于真实的宏观事件覆盖**

**OI/Funding 14 笔缺口**
- ETH 最早的 13-14 笔交易（2025-05-01 → 2025-05-14）落在 CoinGlass 数据起始（2025-05-15）之前
- BTC 全部 45 笔完全覆盖

---

## Score Regression

### Enable Score 对比（12 组合）

| Strategy | Regime | Baseline Score | Enriched Score | Delta | Baseline Status | Enriched Status | Changed |
|----------|--------|---------------|----------------|-------|-----------------|-----------------|---------|
| ATR_ETH_3m | range | 50.73 | 50.73 | 0.000 | 弱开启 | 弱开启 | No |
| ATR_ETH_3m | trend_down | 68.57 | 68.57 | 0.000 | 中等开启 | 中等开启 | No |
| ATR_ETH_3m | trend_up | 76.61 | 76.61 | 0.000 | 中等开启 | 中等开启 | No |
| BAW_ETH_5m | range | 35.23 | 35.23 | 0.000 | 禁用 | 禁用 | No |
| BAW_ETH_5m | trend_down | 60.71 | 60.71 | 0.000 | 弱开启 | 弱开启 | No |
| BAW_ETH_5m | trend_up | 31.59 | 31.59 | 0.000 | 禁用 | 禁用 | No |
| BTP_BTC_1H | range | 33.34 | 33.34 | 0.000 | 禁用 | 禁用 | No |
| BTP_BTC_1H | trend_down | 37.59 | 37.59 | 0.000 | 禁用 | 禁用 | No |
| BTP_BTC_1H | trend_up | 27.48 | 27.48 | 0.000 | 禁用 | 禁用 | No |
| BTP_ETH_30m | range | 57.55 | 57.55 | 0.000 | 弱开启 | 弱开启 | No |
| BTP_ETH_30m | trend_down | 69.36 | 69.36 | 0.000 | 中等开启 | 中等开启 | No |
| BTP_ETH_30m | trend_up | 32.89 | 32.89 | 0.000 | 禁用 | 禁用 | No |

**结论：**
- ✅ Enable Score: **12/12 delta = 0.000000**
- ✅ Status: **12/12 完全一致**
- ✅ Status 分布: **强开启 0 / 中等开启 3 / 弱开启 3 / 禁用 6**

---

## Performance Regression

### Performance Matrix 指标对比

| 指标 | 一致性 | 最大 delta |
|------|--------|-----------|
| trade_count | ✅ | 0 |
| win_rate | ✅ | 0.000000 |
| avg_R | ✅ | 0.000000 |
| median_R | ✅ | 0.000000 |
| total_R | ✅ | 0.000000 |
| profit_factor | ✅ | 0.000000 |
| max_drawdown_R | ✅ | 0.000000 |
| longest_losing_streak | ✅ | 0 |
| current_losing_streak | ✅ | 0 |
| time_under_water_ratio | ✅ | 0.000000 |
| max_recovery_trades | ✅ | 0 |
| average_recovery_trades | ✅ | 0.000000 |

**结论：** ✅ 所有 Performance Matrix 指标完全一致。

### Monte Carlo 对比

- ✅ 所有 MC 字段完全一致（random_seed=42 保证可重复性）

---

## Label Quality Delta

### Quality Score 对比

| Field | Cleaned Unknown | FullYear Unknown | Delta | Cleaned Status | FullYear Status | Interpret |
|-------|----------------|-----------------|-------|----------------|-----------------|-----------|
| session | 0.0% | 0.0% | 0.0% | PASS | PASS | — |
| structure_state | 0.0% | 0.0% | 0.0% | PASS | PASS | — |
| volatility_state | 0.0% | 0.0% | 0.0% | PASS | PASS | — |
| **orderflow_state** | **100.0%** | **86.1%** | **-13.9%** | BLOCK | BLOCK | ✅ 改善但仍 BLOCK |
| **macro_state** | **100.0%** | **0.0%** | **-100.0%** | BLOCK | **PASS** | ✅ 完全解决 (fallback) |

**关键解读：**
- `orderflow_state`: 从 100% unknown → 86.1% unknown（改善 13.9pp），但 86% > 50% threshold → STILL BLOCK
- `macro_state`: 从 100% unknown → 0% unknown → PASS ✅。注意：88% 为 fallback "neutral"，12% 来自 ETF flow→"flow_driven"。这不是"真正的宏观事件覆盖"而是 fallback 逻辑。

---

## Readiness Re-Check

### P2 Feature Readiness

| Feature | P2-5 Readiness | P2-12 FullYear Readiness | Changed | Reason |
|---------|---------------|------------------------|---------|--------|
| Automatic Regime Classifier | BLOCK | BLOCK | No | orderflow_state 86.1% > 50% |
| Market Opportunity Score | BLOCK | BLOCK | No | orderflow_state 86.1% > 50% |
| Layered Regime Analysis | BLOCK | BLOCK | No | orderflow_state 86.1% > 50% |

**Readiness 虽有改善但三种 feature 仍 BLOCK，因 orderflow_state 是 classifier/MO/regime 三方共用的 critical blocker。**

### P2-5 → P2-12 演化：
- P2-5: **3 fields BLOCK** (orderflow + macro 两个)
- P2-9 mock: **1.5 fields BLOCK** (orderflow 90% + macro 0%, 但都是 mock)
- P2-12 full live: **1 field BLOCK** (orderflow 86%), macro ✅

**核心瓶颈：orderflow_state 受 Hobbyist taker 4h 60 天限制。除非升级 CoinGlass plan 或接入其他 orderflow 数据源（如 Binance trades stream），否则 classifier 长期 BLOCK。**

---

## Recommendation

### 1. enriched_trades_full_year.csv 是否可以作为实验输入？
**✅ 可以。**
- Score regression 12/12 delta=0，Performance 100% 一致
- OI/Funding/ETF/macro 全部回填成功
- 适合用于 Partial Feature Review 实验中评估各字段贡献

### 2. 是否建议设为默认评分输入？
**❌ 暂不建议。**
- orderflow_state 86% unknown，与 cleaned_trades.csv 的评分完全一致
- 默认状态分布没有变化
- OI/Funding/ETF 字段当前不在评分逻辑中使用（评分基于 pnl_R / regime / MC）
- 切换收益为零，风险为增加数据路径依赖复杂度

### 3. 是否建议进入 Market Opportunity Score？
**❌ 仍不建议。**
- 核心依赖 orderflow_state，当前 86% unknown → BLOCK
- Market Opp 需要对交易前市场状态做实时/历史评分，unknown 字段无法支撑

### 4. 是否建议进入 automatic classifier？
**❌ 仍不建议。**
- orderflow_state 86% unknown > 50% blocking threshold
- macro_state 虽 PASS 但有 88% 为 fallback "neutral"，非真实宏观事件覆盖
- 但 blocker 从 2 个降至 1 个（P2-5 时 macro 也为 BLOCK）— 实质性进展

### 5. 是否建议先做 Partial Feature Readiness Review (P2-13)？
**✅ 强烈建议。**

P2-13 可以是轻量级的 conditional readiness review：
- 对已满足 readiness 的字段（OI/Funding/ETF/Macro）做 partial feature prototype
- 对 orderflow 缺失制定替代方案评估（降级 plan / 补充数据源 / 降低 classifier 对 orderflow 的权重依赖）
- 可以探索：是否允许 classifier 在 orderflow 部分 missing 时仍工作？是否可以通过 OI+Funding 的组合推导 orderflow 信号？
- **不需要 switch default input**，用 enriched_full_year 作为实验数据

### 6. 是否需要升级 CoinGlass 计划或补充其他数据源？
**建议评估两条路径：**

| 路径 | 描述 | 成本 | 效果 |
|------|------|------|------|
| A. 升级 CoinGlass plan | 获取 1h taker interval + full history | ~$50-200/mo | orderflow_state 覆盖率 ~100% |
| B. 补充 Binance API | 直接抓 trades stream → 自建 taker imbalance | $0 (public) | orderflow_state 覆盖率 ~100%，但需要额外工程 |
| C. 降低 orderflow 依赖 | 在 P2-13 评估 OI+Funding+ETF 是否足以支撑部分 classifier 功能 | $0 | Classifier 在 orderflow 缺失时降级运行 |

---

## 文件清单

### 新增配置
| 文件 | 说明 |
|------|------|
| `config.enriched.live.full.yaml` | P2-12 enrichment config |
| `config.enriched.full_year.pipeline.yaml` | P2-12 enriched pipeline config |

### 新增输出
| 文件/目录 | 说明 |
|----------|------|
| `outputs/data_quality/enriched_trades_full_year.csv` | Full-year enriched CSV |
| `outputs/data_quality/enrichment_audit_report_full_year.md` | Enrichment audit |
| `outputs/validation_enriched_full_year/` | 4 个 pipeline 输出 |
| `outputs/data_quality_full_year/` | Label quality re-check |
| `outputs/full_year_enriched_regression_report.md` | **本报告** |

### 未修改（保护验证）
| 文件 | 状态 |
|------|------|
| `config.yaml` | ✅ input_path 不变 |
| `outputs/data_quality/cleaned_trades.csv` | ✅ |
| `outputs/baseline_cleaned_official/` | ✅ |
| `data/external/coinglass_live_full/processed/` | ✅ |
| `src/strategy_enable_system/` | ✅ P2-10 改动外无新增 |

---

*Generated by Strategy Enable Score System v1.1 — P2-12 Full-Year Label Enrichment + Regression*
