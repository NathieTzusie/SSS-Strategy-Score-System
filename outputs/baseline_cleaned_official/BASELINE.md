# Baseline: cleaned_official_baseline

**名称：** `cleaned_official_baseline`  
**创建时间：** 2026-05-13 23:31 CEST  
**版本：** Strategy Enable Score System v1.1 — P0+P1+P2-1,P2-2,P2-3 完成  

---

## 输入文件

```
outputs/data_quality/cleaned_trades.csv
```

- 来源：`data/combined_trade_log_20260513.csv` 经 P2-2 Label Quality Tool 修复
- 修复内容：`session`（UTC 小时 → Asia/London/NY/overlap/weekend）、`structure_state`（← regime）、`regime_snapshot_id`（归一化）
- 审计列：`original_regime_snapshot_id` 保留原始值

---

## 生成命令

```bash
PYTHONPATH=src python3 -m strategy_enable_system.main --config config.yaml
```

---

## 配置

```yaml
input_path: ["outputs/data_quality/cleaned_trades.csv"]
min_trades: 30
monte_carlo.iterations: 5000
monte_carlo.method: bootstrap
monte_carlo.random_seed: 42
score_thresholds: {strong: 80, medium: 65, weak: 50}
```

---

## 测试结果

```
94/94 passed
```

---

## 状态分布

| Status | Count |
|--------|-------|
| 强开启 | 0 |
| 中等开启 | 3 |
| 弱开启 | 3 |
| 禁用 | 6 |

---

## Enable Score（12 组合）

| Strategy | Regime | Score | Status |
|----------|--------|-------|--------|
| ATR_ETH_3m | trend_up | 76.6 | 中等开启 |
| BTP_ETH_30m | trend_down | 69.4 | 中等开启 |
| ATR_ETH_3m | trend_down | 68.6 | 中等开启 |
| BAW_ETH_5m | trend_down | 60.7 | 弱开启 |
| BTP_ETH_30m | range | 57.6 | 弱开启 |
| ATR_ETH_3m | range | 50.7 | 弱开启 |
| BTP_BTC_1H | trend_down | 37.6 | 禁用 |
| BAW_ETH_5m | range | 35.2 | 禁用 |
| BTP_BTC_1H | range | 33.3 | 禁用 |
| BTP_ETH_30m | trend_up | 32.9 | 禁用 |
| BAW_ETH_5m | trend_up | 31.6 | 禁用 |
| BTP_BTC_1H | trend_up | 27.5 | 禁用 |

---

## 关键风险结论

- **BAW_ETH_5m @ range / trend_up**：MC 尾部回撤 > 80%，TUW > 87%，禁用
- **BTP_BTC_1H 全部 3 regime**：样本不足禁用，trend_down Base=70 有 edge
- **ATR_ETH_3m @ range**：TUW=84%，max_recovery=34 笔，弱开启

---

## 使用说明

- 此 baseline 基于 cleaned CSV
- **P2-3 已验证与原始 CSV 评分零差异（delta = 0.000）**
- 后续 P2 功能开发（P2-4+）应以此 baseline 对照
- 除非任务明确要求，否则**不应再使用原始 CSV 作为默认输入**
- 如需回退原始 CSV，使用 `config.cleaned.yaml` 将 input_path 指向 `data/combined_trade_log_20260513.csv`

---

## 附：输出文件

```
outputs/baseline_cleaned_official/
  performance_matrix.csv
  monte_carlo_results.csv
  enable_score.csv
  summary_report.md
  BASELINE.md                    ← 本文件
```
