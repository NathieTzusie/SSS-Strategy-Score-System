# P2-11 Live Full-Year CoinGlass Fetch — 验收报告

**生成时间：** 2026-05-14 11:20 CEST  
**版本：** Strategy Enable Score System v1.1

---

## Executive Summary

| 项目 | 值 |
|------|-----|
| 是否检测到 API key | yes |
| 是否执行 live fetch | yes |
| symbols | BTC, ETH |
| endpoints | 6 (3 futures × 2 + ETF × 2 + Calendar) |
| 成功 endpoint 数 | 8/9 (89%) |
| 失败 endpoint 数 | 1/9 (financial_calendar: 401 Hobbyist plan) |
| 是否 partial success | yes (calendar failed, 不影响其他) |
| 是否泄露 API key | **no** ✅ |

---

## Trade Time Range

| Symbol | Trade Count | Min Entry Time | Max Entry Time |
|--------|------------|----------------|----------------|
| BTCUSDT | 45 | 2025-05-23 13:00 | 2026-05-07 04:00 |
| ETHUSDT | 471 | 2025-05-01 13:45 | 2026-05-08 12:48 |
| **Total** | **516** | 2025-05-01 13:45 | 2026-05-08 12:48 |

---

## Fetch Results

| Endpoint | Symbol | Interval | Request Params | Raw File | Processed File | Rows | Min UTC | Max UTC | Status |
|----------|--------|----------|---------------|----------|---------------|------|---------|---------|--------|
| open_interest_aggregated | BTC | 1d | limit=365 | `BTC_oi_agg_*.json` | `BTC_oi_agg.csv` | 365 | 2025-05-15 | 2026-05-14 | ✅ |
| open_interest_aggregated | ETH | 1d | limit=365 | `ETH_oi_agg_*.json` | `ETH_oi_agg.csv` | 365 | 2025-05-15 | 2026-05-14 | ✅ |
| funding_oi_weight | BTC | 1d | limit=365 | `BTC_funding_oiw_*.json` | `BTC_funding_oiw.csv` | 365 | 2025-05-15 | 2026-05-14 | ✅ |
| funding_oi_weight | ETH | 1d | limit=365 | `ETH_funding_oiw_*.json` | `ETH_funding_oiw.csv` | 365 | 2025-05-15 | 2026-05-14 | ✅ |
| taker_buy_sell_aggregated | BTC | **4h** | limit=365 | `BTC_taker_agg_*.json` | `BTC_taker_agg.csv` | 365 | 2026-03-14 | 2026-05-14 | ✅ |
| taker_buy_sell_aggregated | ETH | **4h** | limit=365 | `ETH_taker_agg_*.json` | `ETH_taker_agg.csv` | 365 | 2026-03-14 | 2026-05-14 | ✅ |
| bitcoin_etf_flow | BTC | daily | (none) | `btc_etf_flow_*.json` | `btc_etf_flow.csv` | 603 | 2024-01-11 | 2026-05-13 | ✅ |
| ethereum_etf_flow | ETH | daily | (none) | `eth_etf_flow_*.json` | `eth_etf_flow.csv` | 465 | 2024-07-23 | 2026-05-13 | ✅ |
| financial_calendar | GLOBAL | — | ±15d | — | — | — | — | — | ❌ 401 |

**错误详情：**
- `financial_calendar`: HTTP 200, CoinGlass `code=401, msg="Upgrade plan"` — Hobbyist plan 不支持此 endpoint

---

## Coverage Against Trades

| Data Source | Symbol | Trade Start | Trade End | Data Start | Data End | Covers Start | Covers End | Coverage Ratio |
|------------|--------|------------|----------|------------|----------|-------------|-----------|---------------|
| oi_agg | BTC | 2025-05-23 | 2026-05-07 | 2025-05-15 | 2026-05-14 | ✅ | ✅ | **100%** (45/45) |
| oi_agg | ETH | 2025-05-01 | 2026-05-08 | 2025-05-15 | 2026-05-14 | ❌ | ✅ | **97%** (458/471) |
| funding_oiw | BTC | 2025-05-23 | 2026-05-07 | 2025-05-15 | 2026-05-14 | ✅ | ✅ | **100%** (45/45) |
| funding_oiw | ETH | 2025-05-01 | 2026-05-08 | 2025-05-15 | 2026-05-14 | ❌ | ✅ | **97%** (458/471) |
| taker_agg (4h) | BTC | 2025-05-23 | 2026-05-07 | 2026-03-14 | 2026-05-14 | ❌ | ✅ | **11%** (5/45) |
| taker_agg (4h) | ETH | 2025-05-01 | 2026-05-08 | 2026-03-14 | 2026-05-14 | ❌ | ✅ | **14%** (67/471) |
| btc_etf_flow | BTC | 2025-05-23 | 2026-05-07 | 2024-01-11 | 2026-05-13 | ✅ | ✅ | **100%** (45/45) |
| eth_etf_flow | ETH | 2025-05-01 | 2026-05-08 | 2024-07-23 | 2026-05-13 | ✅ | ✅ | **100%** (471/471) |

---

## Endpoint Notes

### taker_buy_sell_aggregated
- ⚠️ **必须使用 4h interval**（Hobbyist plan 下 1h 返回 403）
- limit=365 @ 4h = 约 60 天覆盖，只能覆盖最近 2 个月的 trade
- **全年 orderflow_state 回填需要更高 plan 或接受 2 月覆盖**
- 当前覆盖：BTC ~11%, ETH ~14%

### financial_calendar
- ❌ Hobbyist plan 不支持（code=401 "Upgrade plan"）
- **全年 macro_state 无法使用 event_risk 标签**，只能在 ETF 数据可用时使用 "flow_driven"
- Calendar 的 lookback/lookahead ±15 天本就不支持全年历史回填，此 endpoint 设计用途是实时/近期判断

### ETF Flow
- ✅ 全量覆盖！BTC ETF 从 2024-01-11, ETH ETF 从 2024-07-23
- 日级数据，交易可获取 entry_time 当日前最近的 ETF flow 标签

### OI / Funding
- ✅ OI 和 Funding 1d limit=365 覆盖约 1 年，但 ETH 最早几笔交易（2025-05-01~05-14）有 14 天缺口
- BTC 所有交易完全覆盖（最早 BTC 交易在 2025-05-23，在数据 2025-05-15 之后）

---

## Baseline Protection

| 检查项 | 状态 |
|--------|------|
| config.yaml input_path 未改变 | ✅ `["outputs/data_quality/cleaned_trades.csv"]` |
| cleaned_trades.csv 未修改 | ✅ |
| outputs/baseline_cleaned_official/ 未覆盖 | ✅ |
| config.coinglass.live.small.yaml 未修改 | ✅ |
| P2-10 small batch 数据未覆盖 | ✅ `data/external/coinglass_live_small/` 完好 |
| 默认评分状态分布不变 | ✅ |

---

## Recommendation

### 1. 是否建议进入 P2-12 Full-Year Label Enrichment + Regression？

**✅ 建议。**

OI/Funding/ETF 数据全量覆盖，enrichment 可以大幅回填 4 个字段。Taker 和 Calendar 有限制但在预期内。

### 2. 哪些 endpoint 覆盖足够？

| Endpoint | 覆盖度 | 判断 |
|----------|--------|------|
| open_interest_aggregated | BTC 100%, ETH 97% | ✅ 足够 |
| funding_oi_weight | BTC 100%, ETH 97% | ✅ 足够 |
| bitcoin_etf_flow | BTC 100% | ✅ 足够 |
| ethereum_etf_flow | ETH 100% | ✅ 足够 |
| taker_buy_sell_aggregated (4h) | BTC 11%, ETH 14% | ⚠️ 仅 2 月覆盖 |

### 3. 哪些 endpoint 覆盖不足？

- **taker_buy_sell_aggregated**: 4h limit=365 → 仅 60 天。全年 orderflow_state 需要更高 plan（支持 1h 或更大 limit）
- **financial_calendar**: Hobbyist 不支持。全年 macro_state "event_risk" 标签不可用（但 macro_state 仍可通过 ETF flow→"flow_driven" + fallback "neutral" 覆盖）

### 4. 是否需要调整 interval / endpoint / rate limit？

- rate_limit=30/min: **保持**
- OI/Funding interval=1d: **保持**
- Taker interval=4h: **无法降低**（Hobbyist 计划限制）
- Calendar: **P2-12 放弃此 endpoint**

### 5. 是否仍不建议进入 Market Opportunity Score？

**✅ 仍不建议。** Taker 全量覆盖仍不足，orderflow_state 在 enrichment 后大概率仍 BLOCK。

### 6. 是否仍不建议进入 automatic classifier？

**✅ 仍不建议。** Taker 全年覆盖不足是结构性限制。

**P2-12 enrichment 后如果 macro_state + oi_state + funding_state + etf_flow_state 全部改善，classifier BLOCK 可能仅由 orderflow_state 导致。届时可评估是否降低 classifier 对 orderflow_state 的权重要求。**

---

## 文件清单

### 新增配置
| 文件 | 说明 |
|------|------|
| `config.coinglass.live.full.yaml` | P2-11 full-year fetch config |

### 新增数据
| 目录 | 内容 |
|------|------|
| `data/external/coinglass_live_full/raw/` | 8 raw JSON files |
| `data/external/coinglass_live_full/processed/` | 8 processed CSV files |

### 新增报告
| 文件 | 说明 |
|------|------|
| `outputs/coinglass_live_full/fetch_audit_report.md` | Fetch audit（自动生成） |
| `outputs/coinglass_live_full/full_year_fetch_report.md` | **本报告** |

### 未修改
| 文件/目录 | 状态 |
|-----------|------|
| `config.yaml` | ✅ |
| `config.coinglass.live.small.yaml` | ✅ |
| `outputs/data_quality/cleaned_trades.csv` | ✅ |
| `outputs/baseline_cleaned_official/` | ✅ |
| `data/external/coinglass_live_small/` | ✅ |
| `src/strategy_enable_system/` (除P2-10改动外) | ✅ |

---

*Generated by Strategy Enable Score System v1.1 — P2-11 Live Full-Year CoinGlass Fetch*
