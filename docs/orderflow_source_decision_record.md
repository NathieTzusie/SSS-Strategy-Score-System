# Orderflow Source Decision Record

**版本：** Strategy Enable Score System v1.1  
**阶段：** P2-17  
**日期：** 2026-05-14  
**前置：** P2-16 Orderflow Data Source Plan  
**状态：** 正式决策记录 — 不含实现代码

---

## 1. Executive Summary

| 项目 | 决定 |
|------|------|
| **Primary path** | CoinGlass Startup plan upgrade validation — 复用现有 fetch/cache/enrichment 架构 |
| **Fallback path** | Binance exchange API adapter — CoinGlass 无法满足需求时的备选 |
| **当前 classifier** | **仍 BLOCK** — orderflow_state 14% < 80% |
| **当前 Market Opp** | **仍 BLOCK** — 依赖 orderflow + calendar + 准实时 |
| **可继续使用** | Partial Context Report (P2-14) + Data Quality Monitor (P2-15) |
| **下一步行动** | 用户确认 CoinGlass Startup plan → P2-18/19A 验证 → P2-20 enrichment regression |

### 决策理由

- 用户月度预算 ($80/mo) 覆盖 CoinGlass Startup ($79/mo)
- CoinGlass 已聚合 Binance + OKX + Bybit — 免除多交易所口径对齐
- 现有 `coinglass_fetch.py` → `coinglass_client.py` → `label_enrichment.py` 全链路已验证
- 优先用预算内方案，只在升级不满足需求时回退 Binance adapter
- 不接受昂贵第三方数据商（Kaiko/Amberdata 等），除非用户后续明确批准

---

## 2. User Decision Checklist Summary

| Decision Area | User Choice | Implication |
|---------------|------------|-------------|
| **Budget — monthly** | $80 USD | Fits Startup plan ($79/mo) |
| **Budget — annual** | $960 USD | Fits Startup annual ($948/yr) |
| **Historical coverage** | 12 months | Must confirm CoinGlass limit permits ≥ 365 days @ 4h |
| **Min interval** | 4h acceptable | Hobbyist already supports 4h; 1h preferred but 4h is fallback |
| **Symbols** | BTC + ETH | Current config already covers both |
| **Source preference** | CoinGlass upgrade (primary) | Maximize reuse of existing architecture |
| **Exchange aggregation** | Required | CoinGlass already aggregates Binance/OKX/Bybit |
| **CVD** | Required | Must confirm if Startup plan includes `aggregated-cvd` endpoint |
| **Footprint** | Not required | Simplifies requirements |
| **Priority** | Historical enrichment | Goal: unblock orderflow_state → classifier readiness |
| **Paid source stance** | Preferred free, but budget up to $80/mo | Budget allocation is explicit; fallback to Binance if CoinGlass doesn't deliver |
| **Binance adapter (fallback)** | Secondary path | Free, public API, but requires additional engineering |

---

## 3. Pricing / Plan Fit

### CoinGlass Pricing (from coinglass.com/pricing)

| Plan | Monthly | Annual | Annual/month avg |
|------|---------|--------|-----------------|
| Hobbyist | $29 | — | $29 |
| **Startup** | **$79** | **$948** | **$79** |
| Standard | $299 | — | $299 |
| Professional | $699 | — | $699 |

### Budget Fit

```
User budget:  $80/mo  |  $960/yr
Startup plan: $79/mo  |  $948/yr
             ✅ within budget ($1/mo margin monthly, $12/yr margin annually)
```

**结论：Startup 在预算内。**

### ⚠️ 风险提示

- CoinGlass pricing 页面显示的是平台功能 tier，**API endpoint 权限可能与 tier 不完全对应**
- Startup plan 是否解锁以下 endpoint **需要实际验证**：
  - [ ] Taker 1h interval（Hobbyist 返回 403 "interval not available"）
  - [ ] Taker 4h 12 个月历史（Hobbyist limit=365 @ 4h = ~60 天）
  - [ ] Aggregated CVD
  - [ ] Financial calendar（Hobbyist 返回 401 "Upgrade plan"）
  - [ ] BTC + ETH 全量覆盖
  - [ ] API rate limit 是否提高（Hobbyist 30/min）
- **不要假设 Startup 自动解锁所有 endpoint**

---

## 4. Minimum Acceptance Criteria

CoinGlass upgrade 方案必须满足以下条件才能被接受为 orderflow 数据源（否则回退 Binance adapter）：

### Must-Have

| # | Criterion | Threshold | Why |
|---|-----------|-----------|-----|
| 1 | BTC + ETH 覆盖 | 100% | 当前 516 笔交易中 45 BTC + 471 ETH |
| 2 | 历史覆盖 | ≥ 12 个月 | 覆盖 trade span 2025-05 → 2026-05 |
| 3 | Taker interval | ≤ 4h | 4h 是最低可接受；1h 更优 |
| 4 | 多交易所 aggregated | Binance + OKX + Bybit | CoinGlass 已聚合此三者 |
| 5 | Taker buy/sell volume | 数值，非 null | 用于计算 taker_imbalance |
| 6 | Aggregated CVD | 数值，非 null | 用户明确需要 CVD |
| 7 | API 可重复抓取 | dry-run → live 可重复 | 用于 future updates |
| 8 | 可通过 adapter 转 processed schema | CSV 符合统一 schema | 不破坏 label_enrichment.py |
| 9 | 严格防止 lookahead bias | prevent_lookahead=true | 使用 entry_time 之前最近已完成的 bar |

### Nice-to-Have

| # | Criterion | Why |
|---|-----------|-----|
| 10 | Taker 1h or 15m | 对 30m/5m/3m 策略解释力更强 |
| 11 | Financial calendar | 解锁 macro_state "event_risk" 标签 |
| 12 | API rate limit ≥ 60/min | 更快的 full-year fetch |

### Gate Rule

```
All Must-Have (1-9) = PASS → 进入 CoinGlass P2-18/19A 路线
Any Must-Have 失败        → 进入 Binance P2-18/19B 路线
```

---

## 5. Decision Tree

```
P2-17 Decision Record (this document)
          │
          ▼
    用户确认升级 → CoinGlass Startup?
          │
    ┌─────┴─────┐
    │ YES       │ NO
    ▼           ▼
 P2-18/19A   P2-18/19B
 CoinGlass   Binance
 validation  adapter
    │           │
    ▼           ▼
 Run small validation fetch:
 - taker endpoint + interval
 - CVD endpoint
 - 12 month history
 - BTC + ETH
 - aggregation
    │
    ├─ All Must-Have (1-9) PASS?
    │       │
    │   ┌───┴───┐
    │   YES     NO
    │   │       │
    │   ▼       ▼
    │  P2-20   Switch to
    │  orderflow  Binance
    │  enrichment adapter
    │  regression  │
    │   │         ▼
    │   ▼       P2-19B
    │  orderflow  Binance
    │  coverage   native
    │  ≥ 80%?    fetcher
    │   │         │
    │   ├─ YES → ▼
    │   │       P2-20
    │   │       orderflow
    │   │       enrichment
    │   │       regression
    │   │
    │   ▼
    │  P2-21
    │  Classifier
    │  Readiness
    │  Re-Review
    │
    └───────────────────
       Until then:
       classifier → BLOCK
       Market Opp → BLOCK
       Partial Context → available
```

---

## 6. Updated P2 Roadmap

### P2-18: Orderflow Adapter Interface

| 属性 | 说明 |
|------|------|
| 目标 | 定义统一 processed schema + adapter 接口，支持 CoinGlass / Binance 双路径 |
| 输入 | 本决策记录 + `docs/orderflow_data_source_plan.md` unified schema 定义 |
| 输出 | `src/strategy_enable_system/orderflow_adapter.py` + tests |
| 验收 | adapter interface 定义完成；mock adapter 可生成统一 schema CSV；`label_enrichment.py` 可读取 |
| 风险 | 接口设计过多或不足 |
| **不包含** | 不调用 API，不抓取真实数据 |

### P2-19A: CoinGlass Upgrade Validation Fetch

| 属性 | 说明 |
|------|------|
| 目标 | 用户升级到 Startup plan 后，验证 taker/CVD endpoint + 12 个月数据 |
| 前置 | 用户确认 CoinGlass Startup plan activated |
| 输入 | CoinGlass API (Startup tier) + 统一 schema |
| 输出 | Validation fetch audit report + processed CSV（如果通过） |
| 验收 | Must-Have criteria 1-9 全部验证；明确的 PASS/FAIL 每个 criterion |
| 风险 | Startup plan 可能仍不提供足够历史或 CVD |

### P2-19B: Binance Native Adapter Prototype

| 属性 | 说明 |
|------|------|
| 目标 | 如果 CoinGlass 不满足条件，开发 Binance Futures API 数据 adapter |
| 前置 | P2-19A FAIL 或用户选择不升级 CoinGlass |
| 输入 | Binance Futures API (public) + taker buy/sell volume via klines or aggTrades |
| 输出 | Binance adapter module + processed CSV (unified schema) |
| 验收 | 12 个月 BTC+ETH 数据抓取成功；taker imbalance 可计算；CVD 可计算或标记 unavailable |
| 风险 | Binance aggTrades 历史长度有限；CVD 推导复杂；单交易所数据 |

### P2-20: Orderflow Enrichment Regression

| 属性 | 说明 |
|------|------|
| 目标 | 用 P2-19A 或 P2-19B 的 orderflow 数据回填 orderflow_state，重跑 enrichment + regression |
| 前置 | P2-19 完成（任一成功路径） |
| 输入 | Unified orderflow processed CSV + `outputs/data_quality/cleaned_trades.csv` |
| 输出 | 更新 `enriched_trades.csv` + audit report + label quality re-check + 回归报告 |
| 验收 | orderflow_state coverage ≥ 80%；score regression delta=0；readiness re-check |
| 风险 | 数据质量问题；interval 对齐 |

### P2-21: Classifier Readiness Re-Review

| 属性 | 说明 |
|------|------|
| 目标 | 只有 orderflow_state coverage ≥ 80% 后才重新评估 classifier readiness |
| 前置 | P2-20 orderflow coverage ≥ 80% |
| 输入 | P2-20 regression report + updated label quality |
| 输出 | Updated partial feature readiness review |
| 验收 | Classifier gate 重新判定；如 PASS 则制定 shadow mode prototype 计划 |
| 风险 | 不要因为数据可用就跳过 shadow mode |

---

## 7. Risks

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| **Startup plan 权限不足** — 升级后 taker 1h 仍不可用、CVD 需要更高 plan | 高 | P2-19A 小批量 validation 先于全量 fetch；失败立即切 Binance |
| **4h interval 限制** — 对 3m/5m/30m 策略的 orderflow 解释力有限 | 中 | 接受 4h，在 report 中标注；1h 是 nice-to-have |
| **Binance adapter 开发复杂度** — 历史数据分页、限速、CVD 推导 | 中 | P2-18 先定义统一接口，再实现具体 adapter |
| **单一交易所偏差** — 只用 Binance 不等于全市场 orderflow | 中 | Binance 是最大 perp 市场，偏差可接受但需标注 |
| **不同数据源口径不一致** — CVD vs taker_imbalance 不等价 | 低 | 保留 `source` + `source_quality` 审计字段 |
| **不应为推进 classifier 降低数据要求** | 高 | 硬性 gate：coverage ≥ 80% + ≥ 6 月 + shadow mode |
| **Lookahead bias** — 使用 entry_time 之后的 orderflow 数据回填 | 高 | 继续使用 `prevent_lookahead=true`，`find_most_recent()` 取最近已完成 bar |

---

## 8. Final Recommendation

| 项目 | 建议 |
|------|------|
| **短期（立即）** | 用户确认是否升级到 CoinGlass Startup plan ($79/mo) |
| **短期（如升级）** | 进入 P2-18 → P2-19A validation fetch → 验证 Must-Have 1-9 |
| **短期（如不升级）** | 进入 P2-18 → P2-19B Binance adapter |
| **中期** | 任一路径获取 ≥80% orderflow coverage → P2-20 enrichment regression |
| **长期** | Coverage ≥ 80% + ≥ 6 月 → P2-21 classifier readiness re-review |
| **当前可用** | Partial Context Report + Data Quality Monitor（不依赖 orderflow） |
| **当前 BLOCK** | Classifier + Full Market Opportunity Score |

### 重申

- ❌ **classifier 继续 BLOCK** — 直到 orderflow coverage ≥ 80%
- ❌ **Market Opportunity 继续 BLOCK** — 直到 classifier ready + 准实时数据 + calendar
- ✅ **Partial Context Report** — 继续可用（6/6 included fields PASS）
- ✅ **Data Quality Monitor** — 继续可用（230/230 tests）

---

*Generated by Strategy Enable Score System v1.1 — P2-17 Orderflow Source Decision Record*
