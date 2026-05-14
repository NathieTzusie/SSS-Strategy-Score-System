# Orderflow Data Source Plan

**版本：** Strategy Enable Score System v1.1  
**阶段：** P2-16  
**日期：** 2026-05-14  
**状态：** 规划文档，不含实现代码

---

## 1. Executive Summary

| 问题 | 回答 |
|------|------|
| 当前 blocker | `orderflow_state` 覆盖仅 14% (72/516)，86% unknown |
| 根因 | CoinGlass Hobbyist plan 下 taker 4h limit=365 → 约 60 天覆盖；1h endpoint 返回 403 |
| 当前可否进入 automatic classifier？ | **否。** orderflow 86% unknown > 50% BLOCK threshold |
| 当前可否进入 full Market Opportunity Score？ | **否。** 依赖 orderflow + calendar，两者均不可用 |
| 当前可否继续用 Partial Context Report？ | **是。** 6/6 included fields PASS，但不使用 orderflow |
| 推荐路线 | 先确定 orderflow 数据源方案，再考虑任何自动化决策 |
| 次要依赖 | `financial_calendar` 也返回 401（Hobbyist），但 macro_state 可通过 ETF flow 回填暂时缓解 |

---

## 2. Current Orderflow Coverage

### 现状

| 指标 | 值 |
|------|-----|
| orderflow_state coverage | 14.0% (72/516 trades) |
| orderflow_state unknown | 86.0% (444/516) |
| Label quality score | 14.0 / 100 (BLOCK) |
| Data source | CoinGlass `/api/futures/aggregated-taker-buy-sell-volume/history` |
| Available interval (Hobbyist) | 4h |
| Blocked interval | 1h (403 — Hobbyist plan) |
| limit @ 4h coverage | 365 records → ~60 calendar days |
| BTC coverage | 5/45 (11%) |
| ETH coverage | 67/471 (14%) |

### 回填分布（72 笔已回填交易）

| 值 | 笔数 |
|----|------|
| neutral | 65 |
| bullish | 5 |
| bearish | 2 |

### 限制链

```
Hobbyist plan
  → taker 1h 403
    → 只能使用 4h interval
      → limit=365 @ 4h = ~60 天
        → orderflow only covers 2026-03 to 2026-05
          → 86% unknown → BLOCK
```

### 当前工作状态

- ✅ Partial Context Report 可用（不依赖 orderflow）
- ✅ OI / Funding / ETF 覆盖良好
- ✅ Baseline stability PASS
- ❌ Classifier BLOCK
- ❌ Market Opportunity BLOCK
- ❌ 不可用 orderflow_state 做任何评分或开关决策

---

## 3. Orderflow Use Cases

### A. Historical Label Enrichment

| 属性 | 说明 |
|------|------|
| 用途 | 回填历史交易的 `orderflow_state`，解除 classifier / Market Opp 数据 blocker |
| 最小覆盖 | ≥ 6 个月，建议 12 个月 |
| 最小粒度 | ≤ 1h（建议 15m 或 5m） |
| 品种 | BTC + ETH |
| 输出 | `orderflow_BTC_1h.csv` / `orderflow_ETH_1h.csv` → processed schema |
| 可审计性 | 需要 source traceability |
| 可重复性 | 需可重新下载/重新生成 |

### B. Context Report Enhancement

| 属性 | 说明 |
|------|------|
| 用途 | 只读报告展示 orderflow 环境，辅助人工复盘 |
| 需求级别 | 低 |
| 可接受粒度 | 4h 或 daily |
| 限制 | Informational only，不改变评分 |

### C. Future Market Opportunity Score

| 属性 | 说明 |
|------|------|
| 用途 | 实时或准实时的市场机会判断 |
| 需求级别 | 最高 |
| 粒度要求 | ≤ 15m，建议 5m |
| 延迟要求 | 准实时（分钟级） |
| 验证要求 | 至少 shadow mode 1-3 个月 |

**当前优先级：A > B > C。先用历史 enrichment 解除 BLOCK，再考虑实时。**

---

## 4. Candidate Data Sources

### Option A: Upgrade CoinGlass Plan

| 维度 | 评估 |
|------|------|
| 复用度 | ⭐⭐⭐⭐⭐ 100% 复用现有 `coinglass_fetch.py` → `coinglass_client.py` → `label_enrichment.py` |
| 改动量 | 最小：更新 config interval + limit 即可 |
| 优点 | 已接入、已验证、有 audit report、有 dry-run |
| 缺点 | 成本未知；历史长度 / interval 权限需确认 |
| 风险 | Plan 升级后 taker 1h / CVD / footprint 是否能覆盖 12 个月？ |

**需确认：**
- [ ] taker 1h 是否可用（当前 403）
- [ ] 是否支持 15m / 5m interval
- [ ] aggregated CVD 是否可用
- [ ] footprint 是否可用
- [ ] 历史长度是否 ≥ 12 个月（limit ≥ 8760 @ 1h）
- [ ] 月度 / 年度计划价格
- [ ] API rate limit 是否提高

### Option B: Exchange Native APIs

| 维度 | 评估 |
|------|------|
| 复用度 | ⭐⭐ 需要自建 adapter（fetch + process） |
| 改动量 | 中等：新增 `orderflow_adapter.py` + Binance/Bybit connector |
| 优点 | 可能免费或低成本；原始数据更透明；可分交易所审计 |
| 缺点 | 需要自己计算 CVD / taker imbalance；历史分页复杂；限速严格 |

**候选：**
- Binance Futures API: `/fapi/v1/aggTrades` 或 klines 间接计算
- Bybit / OKX Futures API
- 需处理：spot vs perp 差异、跨交易所聚合、字段一致性

**需确认：**
- [ ] Binance aggTrades 历史可拉多久（通常 7-30 天直接 API）
- [ ] klines 是否可通过 taker buy volume 推导
- [ ] 历史数据是否需要额外下载/购买

### Option C: Historical Data Provider / Data Dump

| 维度 | 评估 |
|------|------|
| 复用度 | ⭐ 需要手动导入或一次性的 import pipeline |
| 改动量 | 小（一次性脚本） |
| 优点 | 适合历史 bulk 回填；格式固定 |
| 缺点 | 不适合持续更新；供应商绑定；格式不统一 |

**候选：**
- Binance data portal（历史 klines 下载）
- Crypto tick data vendors (Kaiko, Amberdata, CoinAPI)
- TradingView data export

**需确认：**
- [ ] 数据是否包含 taker buy/sell 或可推导
- [ ] 是否覆盖所需时间范围
- [ ] 是否有 download automation

### Option D: Hybrid Approach（推荐）

```
Historical backfill → Option C (data dump) or Option A (upgraded API)
                         ↓
               Processed CSV (unified schema)
                         ↓
              label_enrichment.py 读取

Live / incremental → Option A (CoinGlass) or Option B (exchange API)
                         ↓
               Processed CSV (追加)
```

**优势：**
- 不绑定单一供应商
- 历史回填可以一次性解决
- 实时部分可以后续开发
- adapter interface 屏蔽供应商差异

---

## 5. Minimum Data Requirements

### Historical Classifier Unblock

| 要求 | 阈值 | 注释 |
|------|------|------|
| BTC orderflow coverage | ≥ 80% | 覆盖 BTC trades 中 ≥ 36/45 |
| ETH orderflow coverage | ≥ 80% | 覆盖 ETH trades 中 ≥ 377/471 |
| 时间覆盖 | ≥ 6 月，建议 12 月 | aligned with trade span 2025-05 → 2026-05 |
| 粒度 | ≤ 1h | 至少匹配 BTC 1H 策略时间框架 |
| 必需字段 | taker_buy_volume, taker_sell_volume, taker_imbalance | imbalance 可计算 |
| 建议字段 | cvd, oi_at_time | 非必需但提升分析深度 |
| Lookahead bias | 严格防止 | 使用 entry_time 之前最近已完成 bar |
| 可重复性 | 可重新下载/生成 | 数据源 + 处理参数可审计 |

### Market Opportunity Unblock

| 要求 | 阈值 |
|------|------|
| 粒度 | ≤ 15m, 建议 5m |
| 延迟 | 分钟级 |
| Shadow mode | 至少 1-3 月 |
| 稳定更新 | 每日/实时 |

### 当前 Gap

| 要求 | 现状 | Gap |
|------|------|-----|
| orderflow 12 月覆盖 | 60 天 | 缺 10 个月 |
| orderflow 粒度 | 4h | EOD 够用但 1h 更精确 |
| financial calendar | 401 | 依赖 plan 升级 |

---

## 6. Adapter Architecture Proposal

### 目录结构

```
data/external/orderflow/
  raw/
    coinglass/        ← CoinGlass raw JSON
    binance/          ← Binance raw trades/klines
    bybit/            ← Bybit raw data
  processed/
    orderflow_BTC_1h.csv
    orderflow_ETH_1h.csv
    orderflow_BTC_4h.csv
    orderflow_ETH_4h.csv
```

### 统一 Processed Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `time` | int64 (unix ms) | 原始 bar/trade 时间戳 |
| `datetime_utc` | ISO 8601 string | 人可读 UTC 时间 |
| `symbol` | string | BTC / ETH |
| `source` | string | coinglass / binance / bybit |
| `interval` | string | 1h / 4h / 15m / 5m |
| `taker_buy_volume_usd` | float | Taker buy in USD |
| `taker_sell_volume_usd` | float | Taker sell in USD |
| `taker_imbalance` | float | (buy - sell) / (buy + sell) |
| `cvd` | float or null | Cumulative volume delta（可选） |
| `source_quality` | string | raw / derived / estimated |
| `source_endpoint` | string | API endpoint or file source |

### 设计原则

1. **`label_enrichment.py` 只读 processed 目录的统一 schema** — 不直接依赖 CoinGlass / Binance 命名
2. **每个 adapter（coinglass_fetch / binance_fetch）负责** 把原始数据转为统一 processed schema
3. **保留 `source` 字段** — 用于审计和后续分析
4. **taker_imbalance 统一计算** — 如果 adapter 未提供则从 buy/sell 派生
5. **CVD 为可选** — 如果数据源支持则包含

### 与现有架构的关系

```
CoinGlass API → coinglass_fetch.py → raw JSON → procesed CSV
                                                    ↓
Binance API   → orderflow_adapter.py → (new)     processed CSV (unified)
                                                    ↓
                                          label_enrichment.py
                                                    ↓
                                          enriched_trades.csv
```

**改动点：**
- 新增 `orderflow_adapter.py` 模块（或 `data/external/orderflow/` 目录下的 adapter）
- `label_enrichment.py` 的 `load_processed_data()` 需支持从新 processed schema 读取 orderflow。当前它只读 CoinGlass taker，需泛化为读 `orderflow_*.csv`
- 其他文件不变

---

## 7. Recommended Path

### 优先顺序

| 优先级 | 行动 | 理由 |
|--------|------|------|
| **1** | **确认 CoinGlass plan 升级能力** | 如果能升级到支持 1h taker + 12 个月历史 + calendar，则一步到位，复用量最大 |
| **2** | 如果 CoinGlass 升级不可行 → 做 Binance exchange API adapter | 免费、公开 API、覆盖好，但需要额外工程 |
| **3** | 如果两者都不理想 → 数据 dump + adapter 混合 | 历史 bulk import + 轻量级实时 |
| **4** | **不建议用不完整 orderflow 数据进入 classifier** | 14% 覆盖不够，会产生假确定性 |

### 不推荐

- ❌ 不要因为想赶进度用 4h taker → classifier BLOCK 是结构性问题
- ❌ 不要在不确定数据源时对 adapter interface 做过度抽象
- ❌ 不要在 shadow mode 跑通前将 orderflow 接入评分

---

## 8. Proposed Next Tasks

### P2-17 Orderflow Source Decision Checklist

| 属性 | 说明 |
|------|------|
| 目标 | 用户填写决策 checklist，确定数据源路线 |
| 输入 | 本规划文档 |
| 输出 | 填写后的 decision checklist + 选定的数据源 |
| 验收 | checklist 全部填写，数据源明确 |
| 风险 | 计划确认时间长，信息不对称 |

### P2-18 Orderflow Adapter Interface

| 属性 | 说明 |
|------|------|
| 目标 | 实现统一 processed schema + adapter 接口 |
| 输入 | 选定的数据源、unified schema 定义 |
| 输出 | `src/strategy_enable_system/orderflow_adapter.py` + tests |
| 验收 | adapter 接口定义完成；mock adapter 可生成统一 schema CSV；测试通过 |
| 风险 | 接口设计过度或不足 |
| **注意** | 本任务不调用 API，只定义接口和 mock |

### P2-19 Selected Source Fetcher

| 属性 | 说明 |
|------|------|
| 目标 | 根据 P2-17 决策实现具体数据源抓取器 |
| 输入 | P2-17 选定的数据源 + P2-18 adapter 接口 |
| 输出 | 具体 fetcher + raw JSON/CSV + processed CSV（unified schema） |
| 验收 | 12 个月 orderflow 数据成功抓取；processed CSV 符合统一 schema；测试通过 |
| 风险 | API 限速、历史不足、数据质量 |

### P2-20 Orderflow Enrichment Regression

| 属性 | 说明 |
|------|------|
| 目标 | 用 P2-19 的 orderflow 数据重跑 enrichment + readiness + regression |
| 输入 | P2-19 processed CSV + existing enriched_trades_full_year.csv |
| 输出 | Updated enriched CSV；Updated label quality report；回归报告；Readiness re-check |
| 验收 | orderflow_state coverage ≥ 80%；Score regression delta=0；Readiness re-check |
| 风险 | 数据源质量问题；lookahead bias |

---

## 9. Risks

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| **数据源成本** — CoinGlass plan 升级可能月度/年度成本高 | 中 | 先确认价格，再做 ROI 判断。备选 Binance API 免费 |
| **历史长度不足** — 即使升级 plan，某些 endpoint 可能仍有历史限制 | 高 | P2-17 明确确认每个 endpoint 的 limit 上限 |
| **interval 不够细** — 如果 1h 可用但 5m/15m 不可用，Market Opp 仍 BLOCK | 中 | 接受：先解决 classifier，再考虑 Market Opp |
| **跨交易所口径不一致** — Binance taker buy vs CoinGlass aggregated 可能有偏差 | 低 | 使用单一 source 或加权聚合，保留 source 审计 |
| **CVD vs taker_imbalance 不等价** — 两者不是完全相同指标 | 低 | Schema 两者都支持，adapter 标记 source_quality |
| **单一交易所偏差** — 只用 Binance 可能不反映全市场 | 中 | 至少覆盖 BInance + OKX + Bybit 聚合（CoinGlass 已聚合） |
| **过早引入 classifier** — 数据不完整时做 classifier 会产生假确定性 | 高 | 严格的 gate：≥ 80% coverage + ≥ 6 个月 + shadow mode |
| **lookahead bias** — orderflow 数据可能在 entry_time 之后才可用 | 高 | 继续使用 `prevent_lookahead=true` 的 `find_most_recent()` 方法 |

---

## 10. Decision Checklist

> 请逐项勾选或回答，用于 P2-17 决策汇总。

### CoinGlass Plan Upgrade

- [v] 是否愿意考虑升级 CoinGlass plan？
  - 月度心理预算：$__80__/月
  - 年度心理预算：$__960__/年
- [ ] 是否有 CoinGlass plan 档位信息？
  - Hobbyist → Starter/Pro/Enterprise
  - 价格和权限文档链接：___https://www.coinglass.com/zh/pricing___

### Data Requirements

- [ ] 最小历史覆盖：_12_ 个月（建议 12）
- [ ] 最小 interval：
  - [ ] 只接受 1h
  - [v] 可接受 4h
  - [ ] 需要 15m 或更细
- [ ] 品种要求：
  - [v] BTC + ETH
  - [ ] 仅 BTC
  - [ ] 需要更多

### Data Source Preference

- [ ] 优先方案：
  - [v] CoinGlass upgrade（复用现有架构）
  - [ ] Binance exchange API（免费但需自建 adapter）
  - [ ] Historical data dump（一次性 import）
  - [ ] Hybrid
  - [ ] 其他：_次选Binance exchange API_____

### Exchange Coverage

- [ ] 是否需要多交易所 aggregated？
  - [v] 是（CoinGlass 已聚合 BInance/OKX/Bybit）
  - [ ] 否，Binance 单一即可
- [ ] 是否需要 CVD？
  - [v] 是
  - [ ] 否，taker_imbalance 足够
- [ ] 是否需要 Footprint？
  - [ ] 是
  - [v] 否

### Priority

- [ ] 优先目标：
  - [v] Historical enrichment（解除 BLOCK）
  - [ ] Live monitoring（实时 context）
  - [ ] Both

### Budget

- [ ] 是否允许付费数据源？
  - [ ] 是，预算 $______
  - [v] 否，优先免费方案

### Additional Notes

```
(填写其他注意事项)
```

---

*Generated by Strategy Enable Score System v1.1 — P2-16 Orderflow Data Source Plan*
