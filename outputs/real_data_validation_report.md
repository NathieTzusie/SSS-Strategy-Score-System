# Real Data Validation Report — combined_trade_log_20260513.csv

**生成时间：** 2026-05-13 21:50 CEST  
**数据文件：** `data/combined_trade_log_20260513.csv`  
**配置文件：** `config.yaml`（min_trades=30, drawdown_threshold_R=10, seed=42）

---

## 1. 总览

| 指标 | 值 |
|------|-----|
| 总交易数 | 516 |
| 策略数 | 4：ATR_ETH_3m, BAW_ETH_5m, BTP_BTC_1H, BTP_ETH_30m |
| Regime 数 | 3：range, trend_down, trend_up |
| 策略 × regime 组合数 | 12 |

---

## 2. 状态分布

| 状态 | 数量 | 组合 |
|------|------|------|
| **强开启** | 0 | — |
| **中等开启** | 3 | ATR_ETH_3m @ trend_up (76.6), BTP_ETH_30m @ trend_down (69.4), ATR_ETH_3m @ trend_down (68.6) |
| **弱开启** | 3 | BAW_ETH_5m @ trend_down (60.7), BTP_ETH_30m @ range (57.5), ATR_ETH_3m @ range (50.7) |
| **禁用** | 6 | 详见下方 |

---

## 3. 样本数分布

| 策略 | Regime | 笔数 | 样本充足? |
|------|--------|------|-----------|
| BTP_BTC_1H | trend_up | 7 | ⚠️ LOW |
| BTP_BTC_1H | trend_down | 18 | ⚠️ LOW |
| BTP_BTC_1H | range | 20 | ⚠️ LOW |
| BTP_ETH_30m | trend_up | 29 | ⚠️ LOW |
| ATR_ETH_3m | trend_up | 33 | ✅ |
| ATR_ETH_3m | trend_down | 36 | ✅ |
| BTP_ETH_30m | trend_down | 44 | ✅ |
| BTP_ETH_30m | range | 49 | ✅ |
| BAW_ETH_5m | trend_down | 56 | ✅ |
| BAW_ETH_5m | trend_up | 69 | ✅ |
| ATR_ETH_3m | range | 75 | ✅ |
| BAW_ETH_5m | range | 80 | ✅ |

**Low sample 清单（4个组合）：** 全部为 BTP_BTC_1H（3个regime）和 BTP_ETH_30m @ trend_up。BTP_BTC_1H 是较新的策略，天然数据不足。

---

## 4. Score 分布

| 策略 | Regime | Score | 状态 | 惩罚 |
|------|--------|-------|------|------|
| ATR_ETH_3m | trend_up | 76.6 | 中等开启 | — |
| BTP_ETH_30m | trend_down | 69.4 | 中等开启 | — |
| ATR_ETH_3m | trend_down | 68.6 | 中等开启 | — |
| BAW_ETH_5m | trend_down | 60.7 | 弱开启 | MC tail |
| BTP_ETH_30m | range | 57.5 | 弱开启 | — |
| ATR_ETH_3m | range | 50.7 | 弱开启 | MC tail |
| BTP_BTC_1H | trend_down | 37.6 | 禁用 | low_sample + edge_conc |
| BAW_ETH_5m | range | 35.2 | 禁用 | MC tail |
| BTP_BTC_1H | range | 33.3 | 禁用 | low_sample + edge_conc |
| BTP_ETH_30m | trend_up | 32.9 | 禁用 | low_sample + recent_loss + MC + edge |
| BAW_ETH_5m | trend_up | 31.6 | 禁用 | MC tail |
| BTP_BTC_1H | trend_up | 27.5 | 禁用 | low_sample + edge_conc |

**分析：** 分数分布合理，无"直觉强策略被误判为低分"的情况。BTP_BTC_1H 全部禁用主因为样本不足（<30笔），其中 trend_down 的 Base=70 显示策略在统计上有 edge。

---

## 5. 禁用原因分布

| 组合 | 主因 | 详情 |
|------|------|------|
| BAW_ETH_5m @ range | MC 尾部风险 | P(dd>10R)=**85.7%**，worst=-59.1R |
| BAW_ETH_5m @ trend_up | MC 尾部风险 | P(dd>10R)=**81.5%**，worst=-54.4R |
| BTP_BTC_1H @ trend_up | 样本不足 | 7笔 < 30，Base=61，不代表策略失效 |
| BTP_BTC_1H @ range | 样本不足 | 20笔 < 30，Base=56，建议补充数据 |
| BTP_ETH_30m @ trend_up | 样本不足+Base偏低 | 29笔，Base=48，无法区分失效/噪音 |
| BTP_BTC_1H @ trend_down | 样本不足 | 18笔 < 30，**Base=70 显示策略有 edge** |

**关键发现：** BTP_BTC_1H @ trend_down 的 Base=70 说明如果数据充足，该组合有望进入中等开启。目前仅因样本不足被禁用。

---

## 6. Edge Concentration

触发数：**4/12（33%）**

| 组合 | 最大单笔 | Top 5 | 原因 |
|------|---------|-------|------|
| BTP_BTC_1H @ trend_up | 33.5% | 100.0% ⚠️ | 仅7笔交易，样本小导致top_5=100% |
| BTP_BTC_1H @ range | 16.4% | 62.1% ⚠️ | top_5 超 0.60 阈值 |
| BTP_BTC_1H @ trend_down | 18.7% | 70.2% ⚠️ | top_5 超 0.60 阈值 |
| BTP_ETH_30m @ trend_up | 16.5% | 61.8% ⚠️ | top_5 超 0.60 阈值 |

**分析：** 全部 4 个触发组合为小样本（7-29笔），属于正常的样本量不足导致的统计偏差。随着交易量增加，集中度 warning 应会自然消失。**无需调整阈值。**

---

## 7. MC 高尾部风险（P(drawdown > 10R) > 25%）

触发数：**4/12（33%）** ⚠️ 需要重点关注

| 组合 | P(dd>10R) | Worst DD | Score | 状态 |
|------|-----------|----------|-------|------|
| BAW_ETH_5m @ range | **85.7%** | -59.1R | 35.2 | 禁用 |
| BAW_ETH_5m @ trend_up | **81.5%** | -54.4R | 31.6 | 禁用 |
| BAW_ETH_5m @ trend_down | 26.5% | -30.0R | 60.7 | 弱开启 |
| ATR_ETH_3m @ range | 26.2% | -32.0R | 50.7 | 弱开启 |

**🔴 严重警告：BAW_ETH_5m @ range 和 @ trend_up 的 MC 尾部风险极高。**

BAW_ETH_5m 的 PnL 特征：
- @ range：80笔，avg_R=+0.10，PF=1.12 — 微利但高波动（std=2.04R），极端交易 ±5R
- @ trend_up：69笔，avg_R=-0.05，PF=0.93 — 微亏
- @ trend_down：56笔，avg_R=+0.56，PF=2.02 — 表现最好

**根因分析：** BAW_ETH_5m 是 5m 级别的盘整套利策略（Williams Runner）。其 avg_win=+1.8R / avg_loss=-1.6R 意味着 payoff ratio 仅 1.1，盈亏比接近 1:1。虽然 trend_down 下胜率 60.7% 能维持正期望，但在 range 和 trend_up 下胜率仅 43-50%，高波动 + 低盈亏比 → 必然高尾部风险。

---

## 8. 子分数分析

| 组合 | Regime Edge | Recent Health | MC Stability | Risk Control | 弱点 |
|------|-------------|---------------|--------------|--------------|------|
| BAW_ETH_5m @ range | 56 | 53 | **44** | **28** | MC + RC |
| BAW_ETH_5m @ trend_up | 50 | 46 | **36** | **30** | MC + RC |
| ATR_ETH_3m @ range | 61 | 63 | 58 | 57 | 均衡偏低 |
| BTP_ETH_30m @ trend_up | 47 | 56 | 45 | 50 | RE + MC |
| BTP_BTC_1H @ trend_down | 64 | **80** | **78** | 62 | 仅样本不足 |

**BAW_ETH_5m 的 Risk Control 子分数显著低于其他策略（28-30 vs 49-80）**，主要由 avg_loss=-1.6R 和 payoff≈1.1 驱动。这说明该策略的每笔交易风控较弱。

---

## 9. 数据质量

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 必填字段完整性 | ✅ | 全部 9 个核心字段存在 |
| pnl_R 有效性 | ✅ | 无 NaN/非数值 |
| 时间字段 | ✅ | entry/exit 全部可解析，exit ≥ entry |
| direction | ✅ | 仅 long/short |
| trade_id 重复 | ✅ | 无重复 |
| regime 标签 | ✅ | trend_up/trend_down/range，无拼写变体 |
| **session** | ❌ 100% unknown | 所有 516 笔 session = unknown |
| **structure_state** | ❌ 100% unknown | 无结构状态信息 |
| **volatility_state** | ❌ 100% unknown | 无波动率状态信息 |
| **orderflow_state** | ❌ 100% unknown | 无订单流状态信息 |
| **macro_state** | ❌ 100% unknown | 无宏观状态信息 |
| **所有 status 字段** | ❌ 100% unknown | oi/cvd/funding/cbp/etf 全 unknown |
| regime_snapshot_id | ⚠️ 过于碎片化 | **499 个唯一值 / 516 笔交易**（几乎每笔一个） |

**数据质量评估：** 核心交易数据（trade_id, pnl_R, entry/exit, direction, regime）质量良好。但所有市场和状态上下文字段均为 `unknown`，说明上游数据管道尚未填充这些字段。`regime_snapshot_id` 每笔交易一个唯一值，起不到分组作用，不影响评分但 Summary Report 中的 snapshot 分布会非常冗长。

---

## 10. 参数调整建议

| 参数 | 当前值 | 建议 | 理由 |
|------|--------|------|------|
| `min_trades` | 30 | **保持 30** | 大部分 ETH 策略 >30 笔；BTP_BTC_1H 数据不足是事实，不应降低标准 |
| `drawdown_threshold_R` | 10 | **保持 10** | 有效识别了 BAW_ETH_5m 的结构性风险 |
| `score_thresholds` | 80/65/50 | **保持** | 分布合理（0/3/3/6），无堆积 |
| `edge_concentration.*_warning_threshold` | 0.35/0.60/0.70 | **保持** | 4/12 触发均为小样本，非阈值问题 |
| `metric_caps.max_profit_factor` | 10.0 | **保持** | 无触发 cap 的组合 |
| `metric_caps.max_payoff_ratio` | 10.0 | **保持** | 无触发 cap 的组合 |

**不建议调整任何参数。** 当前配置对真实数据的评分结论合理，无系统性误判。

---

## 11. 风险与行动项

| 优先级 | 行动项 | 说明 |
|--------|--------|------|
| 🔴 P0 | **审查 BAW_ETH_5m 实盘风险** | range/trend_up 下 MC 尾部风险 81-86%，worst DD -54~-59R。建议检查是否需要降低仓位或增加止损 |
| 🔴 P0 | **填充状态字段** | 所有分层/状态字段为 unknown，报告中的分层 regime 分布章节无实际信息。建议在上游填充 |
| 🟡 P1 | **降低 regime_snapshot_id 粒度** | 499 个唯一值几乎无分组意义。建议按小时/天聚合，而非每笔一个 snapshot |
| 🟡 P1 | **BTP_BTC_1H 补充数据** | trend_down 的 Base=70 显示潜力。继续收集 BTC 1H 数据，目标每 regime ≥30笔 |
| 🟢 P2 | **session 字段填充** | 全部 unknown，session_distribution 列无意义 |
| 🟢 P2 | **BTP_ETH_30m @ trend_up 观察** | 29笔/Borderline，avg_R=-0.074 微亏。建议收集 ≥30 笔后重评 |

---

## 12. 最终确认

- [x] 所有输出文件生成无异常
- [x] `summary_report.md` 可独立阅读
- [x] 4 个风险分类与实际一致
- [x] 无评分与直觉严重冲突
- [x] 所有禁用组合有可操作的具体原因
- [x] 参数调整建议有明确理由

### 验收结论：✅ 通过

v1.1 在真实数据上的评分逻辑合理、无系统性误判。BAW_ETH_5m 的高 MC 尾部风险是真实信号而非评分 bug。BTP_BTC_1H 的禁用是样本不足导致的正确降权。可以进入 P2。

---

*Report generated by EdiSolary for Strategy Enable Score System v1.1*
