# Real Data Validation Checklist — v1.1 验收基线

> 目标：在进入 P2 前，用真实交易日志 CSV 确认评分逻辑无系统性误判。

---

## 第 1 步：字段完整性检查

- [ ] 所有必填字段存在：`trade_id`, `strategy_name`, `symbol`, `direction`, `entry_time`, `exit_time`, `pnl_R`, `session`, `regime`
- [ ] `pnl_R` 全为有效数值（无空值、无字符串）
- [ ] `entry_time` / `exit_time` 全部可解析为 datetime
- [ ] `exit_time >= entry_time`（无反向时间）
- [ ] `direction` 只有 `long` / `short`
- [ ] 无重复 `trade_id`（或已确认重复合理）
- [ ] `regime` 无缺失值
- [ ] 可选字段缺失值已被自动填充为 `unknown`（检查 outputs CSV 或 log）

**验证方式：**
```bash
PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml 2>&1
# 无 ValueError → 字段校验通过
```

---

## 第 2 步：Regime 标签质量检查

- [ ] `regime` 值分布合理（无过多拼写变体，如 `trend_up` / `TrendUp` / `trend-up` 同时存在）
- [ ] 每个 regime 内的 `structure_state` 与 regime 定义一致（`trend_up` 不应大量包含 `range` 的 structure）
- [ ] `regime_snapshot_id` 粒度合适（不过粗也不过细）
- [ ] 分层字段（`structure_state`, `volatility_state`, `orderflow_state`, `macro_state`）值在预期枚举范围内

**验证方式：**
```bash
# 在 Python 中运行：
python3 -c "
import pandas as pd
df = pd.read_csv('your_real_trades.csv')
print('Regime values:', df['regime'].value_counts().to_dict())
print('Structure states:', df['structure_state'].value_counts().to_dict())
print('Volatility states:', df['volatility_state'].value_counts().to_dict())
"
```
> 如发现 regime 标签混杂或分层字段有大量 `unknown`，建议先清洗数据再评分。

---

## 第 3 步：strategy_name + regime 样本数分布

- [ ] 每个 `(strategy_name, regime)` 组合的 `trade_count` 已记录
- [ ] `trade_count < min_trades` 的组合已确认并理解原因（新策略？特定 regime 少见？）
- [ ] 样本极少的组合（< 10 笔）建议手动检查是否有评估意义

**验证方式：**
```bash
python3 -c "
import pandas as pd
pm = pd.read_csv('outputs/performance_matrix.csv')
print(pm[['strategy_name','regime','trade_count']].to_string())
"
```
> 决策参考：如果大量组合样本 < min_trades，考虑降低 `min_trades` 或合并 regime。

---

## 第 4 步：low_sample 组合清单

- [ ] 所有 `low_sample_warning = True` 的组合已列出
- [ ] 每个低样本组合的 `primary_reason` 明确写 "样本不足"
- [ ] 低样本 + 高 Base Score（≥65）的组合不应被描述为 "策略失效"
- [ ] 决定哪些低样本组合需要收集更多数据后再评估

**验证方式：**
查看 `outputs/summary_report.md` → "风险分类诊断 > 样本不足" 章节。

---

## 第 5 步：Score 分布检查

- [ ] `enable_score` 分布合理（不是全部堆积在某个区间）
- [ ] 强开启 / 中等开启 / 弱开启 / 禁用的比例符合直觉
- [ ] 是否存在"直觉上很强的策略"被评低分 → 检查对应 `penalty_drivers`
- [ ] 是否存在"直觉上很弱的策略"被评高分 → 检查对应 `score_drivers`

**验证方式：**
```bash
python3 -c "
import pandas as pd
es = pd.read_csv('outputs/enable_score.csv')
print(es[['strategy_name','regime','enable_score','status','penalty_drivers']].sort_values('enable_score', ascending=False).to_string())
"
```
> 每发现一个与直觉不符的评分，记录：组合名、分数、怀疑原因、应对措施。

---

## 第 6 步：禁用原因分布检查

- [ ] 禁用的组合清单完整
- [ ] 每个禁用的 `primary_reason` 具体可操作：
  - `样本不足` → 知道需要收集多少数据
  - `MC 尾部回撤风险` → 知道概率和阈值
  - `收益过度集中` → 知道最大单笔占比
  - `连亏恶化` → 知道当前连亏笔数和 Base Score
  - `综合评分过低` → 知道 Base Score 并确认非样本问题
- [ ] 不存在禁用但没有对应 `penalty_drivers` 的组合
- [ ] 不存在禁用但 `review_required = False` 的组合

**验证方式：**
查看 `outputs/summary_report.md` → "策略开启建议 > 禁用" 章节，逐条确认原因。

---

## 第 7 步：Edge Concentration 检查

- [ ] `edge_concentration_warning = True` 的组合已全部列出
- [ ] 每个触发的具体原因明确（largest_win / top_5 / top_10% / 无正盈利）
- [ ] 检查触发比例是否过高：如果 > 50% 组合都触发，检查：
  - 是否 `largest_win_warning_threshold` 太低（当前 0.35）
  - 是否 `top_5_warning_threshold` 太低（当前 0.60）
  - 是否真实数据中确实普遍存在集中度问题
- [ ] 对于触发组合，确认在报告中显示了具体数值而非泛化提示

**验证方式：**
```bash
python3 -c "
import pandas as pd
pm = pd.read_csv('outputs/performance_matrix.csv')
warn = pm[pm['edge_concentration_warning'] == True]
print(f'Edge concentration warning: {len(warn)}/{len(pm)} combos')
print(warn[['strategy_name','regime','largest_win_contribution','top_5_trade_contribution']].to_string())
"
```
> 如果触发率过高，调整 `config.yaml` 中的阈值，或在总结中注明原因。

---

## 第 8 步：参数调整决策

检查以下参数是否需要根据真实数据调整：

- [ ] **`min_trades`**（当前 30）：如果真实数据中大量组合样本 < 20 但仍有评估价值，考虑下调
- [ ] **`drawdown_threshold_R`**（当前 10）：根据实盘最大可承受回撤调整
- [ ] **`score_thresholds`**（当前 80/65/50）：根据策略库的分数分布调整
- [ ] **`edge_concentration.*_warning_threshold`**（当前 0.35/0.60/0.70）：根据触发率调整
- [ ] **`score_weights`**（当前 0.40/0.15/0.25/0.20）：如果想更重视近期表现或更重视长期 edge，调整
- [ ] **`metric_caps`**（当前 10.0）：如果真实数据中 PF 经常被 cap，考虑放宽或收紧

**验证方式：**
- 先跑一次全量，记录第 3-7 步的观察
- 如有需要，修改 `config.yaml` 后重跑
- 对比修改前后的分数分布变化
- 记录修改理由

---

## 第 9 步：最终确认

- [ ] 所有输出文件生成无异常
- [ ] `summary_report.md` 可独立阅读，无需查原始 CSV 也能理解
- [ ] 4 个风险分类（样本不足 / 策略失效 / 市场无机会 / 极端依赖）与实际认知一致
- [ ] 复核清单中的每项都有明确结论或行动项
- [ ] 如有评分与直觉不符的组合 → 已记录原因，决定是否调整参数或标记为需观察

---

## 验收通过标准

| 条件 | 必须满足 |
|------|---------|
| 字段校验无报错 | ✅ |
| 4 个输出文件生成 | ✅ |
| 无评分与直觉严重冲突的组合 | ✅ |
| 所有禁用组合有可操作的具体原因 | ✅ |
| 参数调整有明确理由记录 | ✅ |

---

*Checklist v1.0 — 配合 Strategy Enable Score System v1.1 使用*
