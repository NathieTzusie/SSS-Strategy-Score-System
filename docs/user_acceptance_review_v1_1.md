# 用户验收文档 — Strategy Enable Score System v1.1 RC1

**版本：** v1.1 RC1  
**日期：** 2026-05-14  
**验收人：** Sisie  
**文档用途：** 逐项确认系统是否符合交易工作流、报告是否可读、评分是否可信、限制是否清楚

---

## 1. 验收目标

本次验收要确认：

- [ ] 系统是否能稳定运行（默认 pipeline 无报错）
- [ ] 评分报告是否可读、排名是否符合直觉
- [ ] 策略状态建议（强/中/弱/禁用）是否符合预期
- [ ] 风险提示是否足够清楚（MC 尾部、TUW、Edge Concentration）
- [ ] Partial Context Report 是否对复盘有帮助
- [ ] Data Quality Monitor 是否能提醒关键限制
- [ ] classifier / Market Opportunity 是否被正确拦截（不应实现）

---

## 2. 验收范围

### 包含 ✅

- 默认评分 pipeline（`main.py`）
- `summary_report.md` + 3 CSV 输出
- Partial Context Report（`context_report.py`）
- Data Quality Monitor（`data_quality_monitor.py`）
- README 可复现性
- RC Validation Report

### 明确不包含 ❌

- ❌ Automatic Regime Classifier（仍 BLOCK）
- ❌ Full Market Opportunity Score（仍 BLOCK）
- ❌ 实时行情监控
- ❌ 自动交易
- ❌ CoinGlass 订阅决策（验收后再议）
- ❌ `enriched_trades_full_year.csv` 切换为默认输入（暂不切换）

---

## 3. 验收前置条件

| 项目 | 当前值 | 状态 |
|------|--------|------|
| 版本 | Strategy Enable Score System **v1.1 RC1** | — |
| 测试 | **230/230 passed** | ✅ |
| Baseline 状态分布 | 强开启 0 / 中等开启 3 / 弱开启 3 / 禁用 6 | ✅ |
| Baseline delta | 0.0000000000 | ✅ |
| 默认输入 | `outputs/data_quality/cleaned_trades.csv` | 未切换 |
| RC 验证 | `outputs/release_candidate/RC_VALIDATION_REPORT.md` | PASS |

### 关键输出路径

```
outputs/
  summary_report.md              ← 评分汇总（先看这个）
  enable_score.csv               ← 12 组合评分表
  performance_matrix.csv         ← 14 项表现指标
  monte_carlo_results.csv        ← MC 风险模拟
  context/partial_context_report.md   ← 环境上下文
  monitor/data_quality_monitor_report.md  ← 数据质量
  baseline_cleaned_official/      ← 基准（不可修改）
```

---

## 4. 用户验收清单

每项请勾选 **PASS / WARN / FAIL**。

---

### 类别 A：运行稳定性

- [PASS] **A1. 默认 pipeline 能正常运行**
  - 检查项：`PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml` 无报错
  - 如何判断：输出显示 "Done! Report:" 和 516 trades, 12 combos
  - 备注：

- [PASS] **A2. 输出 4 个核心文件**
  - 检查项：`outputs/performance_matrix.csv`、`monte_carlo_results.csv`、`enable_score.csv`、`summary_report.md`
  - 如何判断：4 个文件都存在且大小 > 0
  - 备注：

- [PASS] **A3. 测试全部通过**
  - 检查项：`PYTHONPATH=src python3 -m pytest tests/ -v` 全部绿色
  - 如何判断：230 passed
  - 备注：

- [PASS] **A4. Baseline 稳定**
  - 检查项：`outputs/baseline_cleaned_official/` 与 `outputs/enable_score.csv` 对比
  - 如何判断：12/12 enable_score delta = 0，status 无变化
  - 备注：

- [PASS] **A5. config.yaml input_path 未被切换**
  - 检查项：`grep input_path config.yaml`
  - 如何判断：仍为 `outputs/data_quality/cleaned_trades.csv`
  - 备注：

---

### 类别 B：评分可信度

- [PASS] **B1. enable_score 排名是否符合直觉**
  - 检查项：打开 `outputs/enable_score.csv`
  - 如何判断：排名合理的策略在顶部，有风险的在底部
  - 备注：ATR_ETH_3m trend_up (76.6) > BTP_ETH_30m trend_down (69.4) > BAW 禁用

- [PASS] **B2. 禁用策略的 primary_reason 是否清楚**
  - 检查项：看禁用策略的 `primary_reason` 列
  - 如何判断：每个禁用都有清晰原因（如 "低样本警告" "高 MC 尾部回撤"）
  - 备注：

- [PASS] **B3. BAW_ETH_5m 风险提示是否充分**
  - 检查项：看 BAW_ETH_5m 三个 regime 的 `risk_notes`
  - 如何判断：MC 尾部回撤 > 80%、TUW > 87%、禁用理由清楚
  - 备注：

- [PASS] **B4. BTP_BTC_1H 是否正确标记为"样本不足"而非"策略失效"**
  - 检查项：BTP_BTC_1H 全部 3 regime 禁用
  - 如何判断：`primary_reason` 指向 low_sample / insufficient data，不混淆为策略失效
  - 备注：

- [PASS] **B5. Recent Health 没有 hard-ban 策略**
  - 检查项：`summary_report.md` 中 recent health 部分
  - 如何判断：近期连亏被标记为 penalty 而非直接禁用
  - 备注：

- [PASS] **B6. review_required 是否合理**
  - 检查项：看哪些 strategy/regime 标记了 `review_required: true`
  - 如何判断：高风险组合应提醒人工复核
  - 备注：

---

### 类别 C：风险报告质量

- [PASS] **C1. Monte Carlo 尾部风险是否清楚**
  - 检查项：`outputs/monte_carlo_results.csv` 的 `probability_drawdown_exceeds_threshold` 列
  - 如何判断：尾部概率用百分比，容易理解
  - 备注：

- [PASS] **C2. TUW / Recovery 风险是否有帮助**
  - 检查项：`performance_matrix.csv` 的 `time_under_water_ratio` / `max_recovery_trades`
  - 如何判断：TUW 高的策略有对应的风险提示
  - 备注：

- [PASS] **C3. Edge Concentration 是否易懂**
  - 检查项：`summary_report.md` 中 edge concentration 章节
  - 如何判断：几笔大盈利占比是否用百分比表示，触发 warning 时有解释
  - 备注：

- [PASS] **C4. low sample warning 是否足够醒目**
  - 检查项：所有 trade_count < 30 的 strategy/regime
  - 如何判断：低样本标记为弱开启或禁用，附带 sample confidence multiplier
  - 备注：

- [PASS] **C5. summary_report.md 是否没有过度预测**
  - 检查项：报告是否写"XXX 预测趋势"或"建议做多/做空"
  - 如何判断：**不应该**包含入场/出场/方向建议。只应有概率和风险陈述
  - 备注：

---

### 类别 D：Partial Context Report

- [PASS] **D1. INFORMATIONAL ONLY 是否清楚**
  - 检查项：`outputs/context/partial_context_report.md`
  - 如何判断：报告开头有醒目的 INFORMATIONAL ONLY 标注
  - 备注：

- [PASS] **D2. included fields 是否有用**
  - 检查项：session / structure / volatility / OI / funding / ETF flow
  - 如何判断：每个 strategy/regime 的 dominant value 和分布有意义
  - 备注：

- [PASS] **D3. excluded fields 是否解释充分**
  - 检查项：报告中 Excluded Fields 章节
  - 如何判断：orderflow / macro / coinbase 排除原因清楚
  - 备注：

- [PASS] **D4. OI / Funding / ETF context 是否对复盘有帮助**
  - 检查项：比如 ATR_ETH_3m range 有 68% flat OI + 79% positive funding
  - 如何判断：这种信息能帮你理解策略在什么环境下执行
  - 备注：

- [PASS] **D5. 没有把 context 当成评分依据**
  - 检查项：context report 是否改变了 enable_score
  - 如何判断：config.yaml input_path 不变，状态分布不变
  - 备注：

---

### 类别 E：Data Quality Monitor

- [PASS] **E1. classifier BLOCK 是否合理**
  - 检查项：`outputs/monitor/data_quality_monitor_report.md`
  - 如何判断：明确写 orderflow 14% < 80% + calendar unavailable
  - 备注：

- [PASS] **E2. Market Opportunity BLOCK 是否合理**
  - 检查项：同上
  - 如何判断：明确写依赖 orderflow + calendar + 准实时
  - 备注：

- [PASS] **E3. Partial Context PASS 是否合理**
  - 检查项：6/6 included fields READY
  - 如何判断：所有 context field coverage ≥ 80%
  - 备注：

- [PASS] **E4. orderflow blocker 是否清楚**
  - 检查项：monitor report 中 taker_4h_coverage 一行
  - 如何判断：明确写 "Hobbyist plan: 4h × 365 = ~60 days"
  - 备注：

- [PASS] **E5. calendar limitation 是否清楚**
  - 检查项：monitor report 中 financial_calendar 一行
  - 如何判断：明确写 "401 under Hobbyist plan"
  - 备注：

- [PASS] **E6. baseline stability 是否清楚**
  - 检查项：monitor report 中 Baseline Stability 章节
  - 如何判断：delta=0, status_changed=0, PASS
  - 备注：

---

### 类别 F：README / 可复现性

- [PASS] **F1. 安装步骤清楚**
  - 检查项：`README.md` 快速开始部分
  - 如何判断：`pip install -r requirements.txt` + 运行命令
  - 备注：

- [PASS] **F2. 默认运行命令清楚**
  - 检查项：`PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml`
  - 如何判断：在 README 中可找到
  - 备注：

- [PASS] **F3. 标签治理命令清楚**
  - 检查项：label_quality 运行命令
  - 如何判断：在 README 中可找到
  - 备注：

- [PASS] **F4. context report 命令清楚**
  - 检查项：`--input` / `--output-dir` 用法
  - 如何判断：在 README Partial Context Report 章节能找到
  - 备注：

- [PASS] **F5. monitor 命令清楚**
  - 检查项：`--config` / `--output-dir` 用法
  - 如何判断：在 README Data Quality Monitor 章节能找到
  - 备注：

- [PASS] **F6. 限制说明清楚**
  - 检查项：README 中是否提到 classifier/Market Opp 不包含
  - 如何判断：Partial Context 和 Monitor 章节说明 INFORMATIONAL ONLY
  - 备注：

---

### 类别 G：交易工作流适配

- [PASS] **G1. 输出适合用于每日/每周策略开关复盘**
  - 检查项：enable_score 是否提供了可操作的评估
  - 如何判断：你可以用 enable_score + summary_report 判断是否需要下线某策略
  - 备注：

- [PASS] **G2. 能帮助克服 bullish bias**
  - 检查项：报告是否给双向或多空中立信息
  - 如何判断：不忽略 bear 场景，MC 尾部风险覆盖空头风险
  - 备注：

- [PASS] **G3. 是否足够中立**
  - 检查项：报告语言不偏向任何方向
  - 如何判断：不用 "强烈建议开启" 或 "该策略极好"
  - 备注：

- [PASS] **G4. 避免直接给买卖建议**
  - 检查项：全文搜索 "做多" / "做空" / "买入" / "卖出"
  - 如何判断：**不应出现**（除非在解释策略名称中）
  - 备注：

- [PASS] **G5. 能作为人工决策辅助**
  - 检查项：看完报告后，你是否更有信息做策略开关决策？
  - 如何判断：报告给你信息，不替你决策
  - 备注：

---

## 5. 用户反馈记录区

| 编号 | 文件/模块 | 问题描述 | 严重度 | 建议修改 | 状态 |
|------|----------|---------|--------|---------|------|
| — | — | — | — | — | — |

**严重度定义：**
- **P0** — 阻止验收。必须在 v1.1 通过前修复。
- **P1** — 应在 v1.1 final 前修复。不影响基本功能但影响体验或准确性。
- **P2** — 后续优化。可在未来版本中逐渐改善。

---

## 6. 验收结论

### A. ✅ 通过验收

```
v1.1 RC1 可标记为 v1.1 Stable。
后续进入使用期 / 监控期。
不立即订阅 CoinGlass。
```

| 条件 | 状态 |
|------|------|
| 所有类别至少 90% PASS | 待确认 |
| 无 P0 反馈 | 待确认 |
| 用户确认报告可读 | 待确认 |

### B. ⚠️ 带条件通过

```
列出必须修复的问题 → 修复后重新跑 RC validation → 重新验收。
```

条件清单：

- [ ] ______
- [ ] ______

### C. ❌ 不通过

```
以下阻塞项必须先解决：
```

阻塞清单：

- [ ] ______
- [ ] ______

---

## 7. 下一步建议

### 如果验收通过 → 

**P2-20 v1.1 Stable Freeze & Documentation Polish**
- 标记 v1.1 为 stable
- 最终整理文档一致性
- 进入使用观察期

### 如果验收发现问题 →

- **先修 P0 / P1 反馈**
- 修完后重新跑 RC validation
- 再重新验收

### 如果用户决定继续 orderflow 路线 →

- 回复 `docs/orderflow_source_decision_record.md` 中的 decision checklist
- 但不建议在验收 **完成前** 订阅 CoinGlass

---

## 8. 附录：关键文件路径

| 文件 | 路径 |
|------|------|
| RC 验证报告 | `outputs/release_candidate/RC_VALIDATION_REPORT.md` |
| RC Checklist | `outputs/release_candidate/RC_CHECKLIST.md` |
| 评分汇总 | `outputs/summary_report.md` |
| 评分表 | `outputs/enable_score.csv` |
| 表现矩阵 | `outputs/performance_matrix.csv` |
| MC 风险 | `outputs/monte_carlo_results.csv` |
| 环境上下文 | `outputs/context/partial_context_report.md` |
| 数据质量监控 | `outputs/monitor/data_quality_monitor_report.md` |
| 基准文档 | `outputs/baseline_cleaned_official/BASELINE.md` |
| 配置文件 | `config.yaml` |
| 使用说明 | `README.md` |
| 功能就绪评审 | `docs/partial_feature_readiness_review.md` |
| Orderflow 决策 | `docs/orderflow_source_decision_record.md` |

---

*Generated by Strategy Enable Score System v1.1 RC1 — P2-19 User Acceptance Review*
