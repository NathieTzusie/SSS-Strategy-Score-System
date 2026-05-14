# Partial Feature Readiness Review

**版本：** Strategy Enable Score System v1.1  
**阶段：** P2-13  
**日期：** 2026-05-14  
**前置：** P2-12 Full-Year Label Enrichment + Regression  
**状态：** 评审文档，不含实现代码

---

## 1. Executive Summary

| 问题 | 回答 |
|------|------|
| 当前是否可以进入 automatic regime classifier？ | **否。** orderflow_state 86.1% unknown > 50% BLOCK threshold |
| 当前是否可以进入 full Market Opportunity Score？ | **否。** 依赖 orderflow + calendar，两者均不可用 |
| 当前是否可以进入 partial/context-only reporting？ | **是。** 5/7 关键字段 READY |
| 当前是否可以使用 enriched_trades_full_year.csv 做实验输入？ | **是。** Score regression 12/12 delta=0，但不建议默认切换 |
| 当前最大 blocker | orderflow_state 覆盖不足（Hobbyist taker 4h limit=365 → 60天） |
| 当前次级风险 | macro_state 32.8% 为 fallback "neutral"，非真实 macro event coverage |
| 当前平台能力 | OI 97.3% / Funding 97.5% / ETF 100% / Session 100% / Structure 100% / Volatility 100% |

---

## 2. Current Field Readiness

| Field | Coverage Rate | Unknown Rate | Readiness | Source | Caveat |
|-------|-------------|-------------|-----------|--------|--------|
| session | 100% | 0% | **PASS** | UTC hour → session label | 非外部数据，内置规则 |
| structure_state | 100% | 0% | **PASS** | regime → structure_state | 直接复制，非推断 |
| volatility_state | 100% | 0% | **PASS** | 原始 trade log | 来源未知，未经外部验证 |
| **oi_state** | **97.3%** | **2.7%** | **READY_FOR_CONTEXT** | CoinGlass OI 1d × 365 | 14笔 ETH 2025-05-01~14 在数据外 |
| **funding_state** | **97.5%** | **2.5%** | **READY_FOR_CONTEXT** | CoinGlass Funding 1d × 365 | 13笔 ETH 2025-05-01~14 在数据外 |
| **etf_flow_state** | **100%** | **0%** | **READY_FOR_CONTEXT** | CoinGlass BTC/ETH ETF daily | 日级数据，3m/5m 交易精度有限 |
| **macro_state** | **100%** | **0%** | **DEGRADED_PASS** | ETF flow → flow_driven (67.2%) + fallback neutral (32.8%) | 无 financial calendar (401 Hobbyist)，"event_risk" 不可用。不能视为真实宏观事件覆盖 |
| **orderflow_state** | **14.0%** | **86.1%** | **BLOCK** | CoinGlass Taker 4h × 365 | Hobbyist 60 天覆盖。BTC 11%, ETH 14% 回填。Classifier/MO/Analysis 三方公用的 critical blocker |

### 分布详情（来自 enriched_trades_full_year.csv）

| Field | 分布 |
|-------|------|
| oi_state | flat 316 (61.2%), rising 103 (20.0%), falling 83 (16.1%), unknown 14 (2.7%) |
| funding_state | positive 409 (79.3%), negative 91 (17.6%), neutral 3 (0.6%), unknown 13 (2.5%) |
| etf_flow_state | inflow 193 (37.4%), neutral 169 (32.8%), outflow 154 (29.8%) |
| orderflow_state | unknown 444 (86.1%), neutral 65 (12.6%), bullish 5 (1.0%), bearish 2 (0.4%) |
| macro_state | flow_driven 347 (67.2%), neutral 169 (32.8%) |

---

## 3. Feature Readiness Matrix

### A. Automatic Regime Classifier

| 属性 | 值 |
|------|-----|
| 状态 | **BLOCK** |
| 原因 | orderflow_state 86.1% unknown > 50%；macro_state 32.8% fallback neutral |
| 关键缺失 | LTF orderflow / CVD / coinbase premium / financial calendar event labels |
| 建议 | **不实现。** 需要升级 CoinGlass plan 或接入其他 orderflow 数据源 |

### B. Full Market Opportunity Score

| 属性 | 值 |
|------|-----|
| 状态 | **BLOCK** |
| 原因 | Market Opportunity 需要实时/准实时 orderflow；当前仅 60 天 4h 历史覆盖 |
| 关键缺失 | orderflow beyond 60d 历史、financial calendar、准实时数据 pipeline |
| 建议 | **不实现。** 比 classifier 要求更高 |

### C. Partial Context Report

| 属性 | 值 |
|------|-----|
| 状态 | **READY** |
| 可用字段 | oi_state, funding_state, etf_flow_state, session, structure_state, volatility_state |
| 允许用途 | 解析当前环境、辅助人工复盘、生成只读 context summary |
| 禁止用途 | 自动开关策略依据、评分乘数、activation multiplier |
| 风险 | ETF flow 是日级，不直接解释 intraday 交易；macro_state 无真实 event labels |
| 建议 | **进入 P2-14 实现。** 轻量级只读报告，不改变评分系统 |

### D. Degraded Market Opportunity Prototype

| 属性 | 值 |
|------|-----|
| 状态 | **RESEARCH_ONLY** |
| 允许 | 离线实验，用 OI+Funding+ETF 组合做相关性分析 |
| 禁止 | 接入 Enable Score、改动 status、上线运行 |
| 建议 | 如果 P2-14 完成后仍有兴趣，可考虑 P2-15 离线探索实验 |

### E. Data Quality Monitor

| 属性 | 值 |
|------|-----|
| 状态 | **READY** |
| 原因 | label_quality + enrichment audit 已具备数据质量监控基础 |
| 建议 | 可在 P2-14 完成后作为轻量级独立功能开发 |

---

## 4. Degraded Mode 设计

### 名称：`partial_context_mode`

### 输入字段

| 级别 | 字段 |
|------|------|
| ALLOW | oi_state, funding_state, etf_flow_state, session, structure_state, volatility_state |
| BLOCK | orderflow_state（至 coverage >= 80%） |
| BLOCK | macro_state "event_risk" 标签（至 financial calendar 可用） |
| BLOCK | coinbase_premium_state（无可靠数据源） |

**注意：** macro_state 仍可输出，但须标注 "fallback-based" 而非 "calendar-verified"。当前 ETF flow→flow_driven (67.2%) 可用；neutral (32.8%) 为 fallback。

### 输出

| 输出 | 内容 |
|------|------|
| `context_report.md` | 每个 strategy/regime 的字段状态分布 + 标签覆盖统计 |
| `context_summary.csv` | 结构化 summary 供下游消费 |

### 规则

1. 所有输出标注 **INFORMATIONAL ONLY** — 不改变 Enable Score
2. 不改变 status（强开启/中等开启/弱开启/禁用）
3. 不触发自动开启/禁用策略
4. 不产生 activation multiplier
5. 如果某字段 readiness 退化到 WARN/BLOCK，报告必须标注
6. 报告开头写明：**本报告不是 trading signal，不替代 Enable Score**

---

## 5. Minimum Requirements To Unblock Features

### Automatic Regime Classifier

| 条件 | 当前状态 | 缺口 |
|------|---------|------|
| orderflow_state coverage >= 80% | 14.0% | ❌ 需要升级 plan 或接入其他数据源 |
| macro true event coverage >= 80% | 0% | ❌ 需要 financial calendar（Hobbyist 不可用） |
| >= 3-6 months stable data | OI/Funding ✅ | orderflow/macro ❌ |
| OOS / Walk-forward validation | 未开始 | |
| 输出先只作 report | 设计就绪 | |

**最低路径：** 升级 CoinGlass plan → 获取 1h taker + calendar → 覆盖跃升至 ~100% → 至少 3 月数据 → 开发 classifier → shadow mode 验证

### Market Opportunity Score

| 条件 | 说明 |
|------|------|
| orderflow >= 80% | 同 classifier |
| 更高频/准实时数据 | Hobbyist 30/min API limit 可能不足 |
| macro event calendar | 需 financial calendar endpoint |
| Shadow mode 先验证 | 必须 |

### Data Quality Monitor

| 条件 | 状态 |
|------|------|
| 当前已满足 | ✅ |

### Partial Context Report

| 条件 | 状态 |
|------|------|
| 当前已满足 | ✅ |

---

## 6. Recommended Next Step

**强烈建议：P2-14 Partial Context Report。**

理由：
- 当前 blocker 是结构性限制（Hobbyist plan 无法支撑 orderflow + calendar），短期无法解除
- 但 OI/Funding/ETF 三字段已就绪，覆盖率 97-100%，数据质量可靠
- 与其空等 plan 升级，不如先用已有字段建立上下文报告能力
- 上下文报告不改变评分系统，零风险
- 完成后可天然衔接 Data Quality Monitor (P2-14A) 或 Degraded Market Opp 离线实验 (P2-15)

**不建议** 下一步做 classifier 或 Market Opportunity Score。

---

## 7. Risk Warnings

1. ⚠️ **不要因 OI/Funding/ETF 覆盖好就贸然实现 classifier。** 高覆盖 ≠ 信号质量。当前系统目标是评分策略启用与否，不是自动交易。

2. ⚠️ **ETF flow 是日级数据。** 不适用于直接解释 3m/5m/30m 交易入场条件。ETF flow→flow_driven 是粗糙的环境标签，不应细粒度解释。

3. ⚠️ **Funding 和 OI 是 derivatives context。** 他们反映衍生品市场状态，不等同于 orderflow（买/卖失衡）。用 funding_state + oi_state 推导"市场方向"有逻辑跳跃风险。

4. ⚠️ **macro_state fallback neutral 不等同于"没有宏观风险"。** 32.8% 的 neutral 标签意味着这段时间内外部数据不可知，不代表真实无风险。

5. ⚠️ **任何 Market Opportunity Score 必须先 shadow mode 运行。** 至少 3-6 个月 shadow 数据、回测验证、假阳/假阴率分析后，才能考虑接入 Enable Score。

6. ⚠️ **当前系统目标仍是策略启用评分。** 不要因为标签丰富了就把系统升级为交易决策引擎。系统边界应明确：Enable Score → 人工决策，不是 Enable Score → 自动交易。

---

## 8. Proposed P2-14 Task Brief

### 任务：P2-14 Partial Context Report

**目标：**
用 `enriched_trades_full_year.csv` 生成只读上下文报告，展示每个 strategy/regime 组合的环境标签分布。不改变 Enable Score。

**输入：**
- `outputs/data_quality/enriched_trades_full_year.csv`（P2-12 生成）
- `outputs/data_quality_full_year/label_quality_summary.csv`（P2-12 生成）

**输出：**
- `outputs/context/partial_context_report.md`
- `outputs/context/partial_context_summary.csv`

**报告应包含：**
- 每个 strategy/regime 的：
  - 交易笔数
  - OI 状态分布（rising/flat/falling）
  - Funding 状态分布（positive/negative/neutral）
  - ETF flow 状态分布（inflow/outflow/neutral）
  - Session 分布（Asia/London/NY/overlap/weekend）
  - Structure 状态分布
  - Volatility 状态分布
  - 标签覆盖情况（每个字段的 filled/unknown ratio）
- 全局 summary 表
- 明确标注：INFORMATIONAL ONLY — 不构成交易建议，不替代 Enable Score

**不做：**
- 不改变 Enable Score
- 不改变 status
- 不修改 config.yaml input_path
- 不修改 cleaned_trades.csv
- 不生成 activation multiplier
- 不实现 classifier
- 不实现 Market Opportunity Score

**验收标准：**
- 测试 176/176 通过
- 不改变 baseline (0/3/3/6)
- config.yaml 未修改
- 报告标注 informational only
- 报告包含字段覆盖统计

---

## 9. 修改记录

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `docs/partial_feature_readiness_review.md` | 本文件 |
| 无修改 | 所有源代码/配置 | 纯文档任务 |

---

*Generated by Strategy Enable Score System v1.1 — P2-13 Partial Feature Readiness Review*
