# Strategy Enable Score System v1.1 — Summary Report
**生成时间：** 2026-05-14 10:15:47
**数据文件：** outputs/data_quality/enriched_trades.csv

## 策略评分总览

| strategy_name | regime | enable_score | final_activation_score | status | review_required | low_sample_warning | edge_concentration_warning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ATR_ETH_3m | trend_up | 76.61 | 76.61 | 中等开启 | False | False | False |
| BTP_ETH_30m | trend_down | 69.36 | 69.36 | 中等开启 | False | False | False |
| ATR_ETH_3m | trend_down | 68.57 | 68.57 | 中等开启 | False | False | False |
| BAW_ETH_5m | trend_down | 60.71 | 60.71 | 弱开启 | True | False | False |
| BTP_ETH_30m | range | 57.55 | 57.55 | 弱开启 | False | False | False |
| ATR_ETH_3m | range | 50.73 | 50.73 | 弱开启 | True | False | False |
| BTP_BTC_1H | trend_down | 37.59 | 37.59 | 禁用 | True | True | True |
| BAW_ETH_5m | range | 35.23 | 35.23 | 禁用 | True | False | False |
| BTP_BTC_1H | range | 33.34 | 33.34 | 禁用 | True | True | True |
| BTP_ETH_30m | trend_up | 32.89 | 32.89 | 禁用 | True | True | True |
| BAW_ETH_5m | trend_up | 31.59 | 31.59 | 禁用 | True | False | False |
| BTP_BTC_1H | trend_up | 27.48 | 27.48 | 禁用 | True | True | True |

## 状态分布
- **强开启：** 0 个组合
- **中等开启：** 3 个组合
- **弱开启：** 3 个组合
- **禁用：** 6 个组合

## 策略开启建议
无强开启组合。
### 🟡 中等开启
- **ATR_ETH_3m** @ trend_up — Score: 76.6
  > 中等开启：基础指标可接受，部分子分数偏低
- **BTP_ETH_30m** @ trend_down — Score: 69.4
  > 中等开启：基础指标可接受，部分子分数偏低
- **ATR_ETH_3m** @ trend_down — Score: 68.6
  > 中等开启：基础指标可接受，部分子分数偏低
### 🟠 弱开启
- **ATR_ETH_3m** @ range — Score: 50.7
  > 弱开启：high_mc_tail_drawdown等风险因素存在
- **BAW_ETH_5m** @ trend_down — Score: 60.7
  > 弱开启：high_mc_tail_drawdown等风险因素存在
- **BTP_ETH_30m** @ range — Score: 57.5
  > 弱开启：表现不稳定或样本不足
### 🔴 禁用
- **BAW_ETH_5m** @ range — Score: 35.2
  > 禁用主因：Monte Carlo 尾部回撤风险过高。P(drawdown > 10.0R) = 85.7%
- **BAW_ETH_5m** @ trend_up — Score: 31.6
  > 禁用主因：Monte Carlo 尾部回撤风险过高。P(drawdown > 10.0R) = 81.5%
- **BTP_BTC_1H** @ trend_up — Score: 27.5
  > 禁用主因：样本不足（7 < 30），当前结论不代表策略必然失效。Base Score 61 处于边界，建议补充数据后重评
- **BTP_BTC_1H** @ range — Score: 33.3
  > 禁用主因：样本不足（20 < 30），当前结论不代表策略必然失效。Base Score 56 处于边界，建议补充数据后重评
- **BTP_ETH_30m** @ trend_up — Score: 32.9
  > 禁用主因：样本不足（29 < 30）且 Base Score 48 偏低，无法区分「策略失效」与「噪音波动」。建议先补充数据再评估
- **BTP_BTC_1H** @ trend_down — Score: 37.6
  > 禁用主因：样本不足（18 < 30），当前结论不代表策略失效。Base Score 70 显示策略在统计层面有 edge，增加样本后可重新评估

## 风险分类诊断

### 📊 样本不足
以下 4 个组合因样本不足导致评分降低——**不代表策略失效**：
- BTP_BTC_1H @ trend_up
- BTP_BTC_1H @ range
- BTP_ETH_30m @ trend_up
- BTP_BTC_1H @ trend_down
> 建议：收集 ≥ 30 笔交易后重新评估。

### ❌ 策略可能失效
以下组合 Base Score 低（长期指标恶化），**策略在当前 regime 下可能不再有效**：
- BAW_ETH_5m @ range
- BAW_ETH_5m @ trend_up

### 🌤️ 市场暂时无机会
无此类别组合。

### 🎯 极端盈利依赖
以下组合收益过度依赖少数极端交易——**不宜仅凭总收益判断稳定性**：
- BTP_BTC_1H @ trend_up
- BTP_BTC_1H @ range
- BTP_ETH_30m @ trend_up
- BTP_BTC_1H @ trend_down

### 📉 MC 尾部风险过高
以下组合 Monte Carlo 模拟显示高概率大幅回撤：
- BAW_ETH_5m @ range
- BAW_ETH_5m @ trend_up

## 风险详情
### ⚠️ 样本不足（< 30笔）
- **BTP_BTC_1H** @ trend_up — 7 笔交易
- **BTP_BTC_1H** @ range — 20 笔交易
- **BTP_ETH_30m** @ trend_up — 29 笔交易
- **BTP_BTC_1H** @ trend_down — 18 笔交易

### ⚠️ Edge Concentration 风险
以下组合可能依赖少数极端行情。触发详情：

- **BTP_BTC_1H** @ trend_up
  - 最大单笔盈利占比 = 33.5%
  - Top 5 盈利占比 = 100.0% ⚠️
  - Top 10% 盈利占比 = 33.5%
  - Gini (正收益) = 0.24
- **BTP_BTC_1H** @ range
  - 最大单笔盈利占比 = 16.4%
  - Top 5 盈利占比 = 62.1% ⚠️
  - Top 10% 盈利占比 = 32.2%
  - Gini (正收益) = 0.30
- **BTP_ETH_30m** @ trend_up
  - 最大单笔盈利占比 = 16.5%
  - Top 5 盈利占比 = 61.8% ⚠️
  - Top 10% 盈利占比 = 28.9%
  - Gini (正收益) = 0.38
- **BTP_BTC_1H** @ trend_down
  - 最大单笔盈利占比 = 18.7%
  - Top 5 盈利占比 = 70.2% ⚠️
  - Top 10% 盈利占比 = 36.0%
  - Gini (正收益) = 0.40

### ⚠️ Monte Carlo 尾部风险偏高
- **BAW_ETH_5m** @ range — P(drawdown > 10.0R) = 85.7%
- **BAW_ETH_5m** @ trend_up — P(drawdown > 10.0R) = 81.5%
- **ATR_ETH_3m** @ range — P(drawdown > 10.0R) = 26.2%
- **BAW_ETH_5m** @ trend_down — P(drawdown > 10.0R) = 26.5%

### ⚠️ 近期表现恶化
- **BTP_ETH_30m** @ trend_up — 当前连亏 4 笔
> 注意：Recent Health 恶化只降权不 hard-ban。如长期 Regime Edge 仍健康，可能为市场环境问题。

### 🔍 需要人工复核（8 个组合）
- **BAW_ETH_5m** @ range — Score: 35.2
  > MC尾部风险偏高：P(drawdown > 10.0R) = 85.7%
- **BAW_ETH_5m** @ trend_up — Score: 31.6
  > MC尾部风险偏高：P(drawdown > 10.0R) = 81.5%
- **BTP_BTC_1H** @ trend_up — Score: 27.5
  > 样本不足（7 < 30），结果仅供参考; 该组合可能依赖少数极端行情，不宜仅凭总收益判断稳定性
- **BTP_BTC_1H** @ range — Score: 33.3
  > 样本不足（20 < 30），结果仅供参考; 该组合可能依赖少数极端行情，不宜仅凭总收益判断稳定性
- **BTP_ETH_30m** @ trend_up — Score: 32.9
  > 样本不足（29 < 30），结果仅供参考; 该组合可能依赖少数极端行情，不宜仅凭总收益判断稳定性; MC尾部风险偏高：P(drawdown > 10.0R) = 15.1%; 当前连亏4笔，近期表现恶化
- **ATR_ETH_3m** @ range — Score: 50.7
  > MC尾部风险偏高：P(drawdown > 10.0R) = 26.2%
- **BAW_ETH_5m** @ trend_down — Score: 60.7
  > MC尾部风险偏高：P(drawdown > 10.0R) = 26.5%
- **BTP_BTC_1H** @ trend_down — Score: 37.6
  > 样本不足（18 < 30），结果仅供参考; 该组合可能依赖少数极端行情，不宜仅凭总收益判断稳定性

## Market State Snapshot 分布 (regime_snapshot_id)

每个 (strategy, regime) 组合内的 market state snapshot 分布：

**BAW_ETH_5m** @ range (80 笔交易)：
- range_W13_2026：8 (10%)
- range_W26_2025：6 (8%)
- range_W01_2026：5 (6%)
- range_W25_2025：4 (5%)
- range_W44_2025：4 (5%)
- range_W49_2025：4 (5%)
- range_W50_2025：4 (5%)
- range_W11_2026：4 (5%)
- range_W14_2026：4 (5%)
- range_W18_2025：3 (4%)
- range_W51_2025：3 (4%)
- range_W02_2026：3 (4%)
- range_W05_2026：3 (4%)
- range_W23_2025：2 (2%)
- range_W24_2025：2 (2%)
- range_W38_2025：2 (2%)
- range_W41_2025：2 (2%)
- range_W42_2025：2 (2%)
- range_W52_2025：2 (2%)
- range_W12_2026：2 (2%)
- range_W15_2026：2 (2%)
- range_W27_2025：1 (1%)
- range_W28_2025：1 (1%)
- range_W37_2025：1 (1%)
- range_W39_2025：1 (1%)
- range_W40_2025：1 (1%)
- range_W43_2025：1 (1%)
- range_W04_2026：1 (1%)
- range_W10_2026：1 (1%)
- range_W19_2026：1 (1%)

**BAW_ETH_5m** @ trend_up (69 笔交易)：
- trend_up_20250529：3 (4%)
- trend_up_20260317：3 (4%)
- trend_up_20250508：2 (3%)
- trend_up_20250511：2 (3%)
- trend_up_20250513：2 (3%)
- trend_up_20250519：2 (3%)
- trend_up_20250522：2 (3%)
- trend_up_20250526：2 (3%)
- trend_up_20250610：2 (3%)
- trend_up_20250612：2 (3%)
- trend_up_20250722：2 (3%)
- trend_up_20250726：2 (3%)
- trend_up_20250807：2 (3%)
- trend_up_20250809：2 (3%)
- trend_up_20250824：2 (3%)
- trend_up_20250826：2 (3%)
- trend_up_20251006：2 (3%)
- trend_up_20260419：2 (3%)
- trend_up_20250512：1 (1%)
- trend_up_20250515：1 (1%)
- trend_up_20250516：1 (1%)
- trend_up_20250521：1 (1%)
- trend_up_20250524：1 (1%)
- trend_up_20250525：1 (1%)
- trend_up_20250601：1 (1%)
- trend_up_20250603：1 (1%)
- trend_up_20250605：1 (1%)
- trend_up_20250611：1 (1%)
- trend_up_20250712：1 (1%)
- trend_up_20250717：1 (1%)
- trend_up_20250720：1 (1%)
- trend_up_20250724：1 (1%)
- trend_up_20250725：1 (1%)
- trend_up_20250728：1 (1%)
- trend_up_20250729：1 (1%)
- trend_up_20250806：1 (1%)
- trend_up_20250812：1 (1%)
- trend_up_20250819：1 (1%)
- trend_up_20250827：1 (1%)
- trend_up_20250901：1 (1%)
- trend_up_20250913：1 (1%)
- trend_up_20250918：1 (1%)
- trend_up_20251005：1 (1%)
- trend_up_20260114：1 (1%)
- trend_up_20260318：1 (1%)
- trend_up_20260411：1 (1%)
- trend_up_20260418：1 (1%)
- trend_up_20260426：1 (1%)
- trend_up_20260504：1 (1%)

**ATR_ETH_3m** @ trend_up (33 笔交易)：
- trend_up_20250508：1 (3%)
- trend_up_20250509：1 (3%)
- trend_up_20250510：1 (3%)
- trend_up_20250516：1 (3%)
- trend_up_20250522：1 (3%)
- trend_up_20250530：1 (3%)
- trend_up_20250531：1 (3%)
- trend_up_20250604：1 (3%)
- trend_up_20250605：1 (3%)
- trend_up_20250702：1 (3%)
- trend_up_20250710：1 (3%)
- trend_up_20250715：1 (3%)
- trend_up_20250719：1 (3%)
- trend_up_20250730：1 (3%)
- trend_up_20250805：1 (3%)
- trend_up_20250808：1 (3%)
- trend_up_20250816：1 (3%)
- trend_up_20250818：1 (3%)
- trend_up_20250820：1 (3%)
- trend_up_20250821：1 (3%)
- trend_up_20250823：1 (3%)
- trend_up_20250824：1 (3%)
- trend_up_20250831：1 (3%)
- trend_up_20250912：1 (3%)
- trend_up_20250918：1 (3%)
- trend_up_20251003：1 (3%)
- trend_up_20251006：1 (3%)
- trend_up_20260114：1 (3%)
- trend_up_20260118：1 (3%)
- trend_up_20260407：1 (3%)
- trend_up_20260411：1 (3%)
- trend_up_20260413：1 (3%)
- trend_up_20260416：1 (3%)

**BTP_BTC_1H** @ trend_up (7 笔交易)：
- trend_up_20250523：1 (14%)
- trend_up_20250718：1 (14%)
- trend_up_20250719：1 (14%)
- trend_up_20250721：1 (14%)
- trend_up_20260416：1 (14%)
- trend_up_20260418：1 (14%)
- trend_up_20260507：1 (14%)

**BTP_BTC_1H** @ range (20 笔交易)：
- range_W51_2025：2 (10%)
- range_W02_2026：2 (10%)
- range_W03_2026：2 (10%)
- range_W11_2026：2 (10%)
- range_W22_2025：1 (5%)
- range_W24_2025：1 (5%)
- range_W31_2025：1 (5%)
- range_W33_2025：1 (5%)
- range_W35_2025：1 (5%)
- range_W41_2025：1 (5%)
- range_W44_2025：1 (5%)
- range_W04_2026：1 (5%)
- range_W05_2026：1 (5%)
- range_W10_2026：1 (5%)
- range_W13_2026：1 (5%)
- range_W17_2026：1 (5%)

**BTP_ETH_30m** @ trend_up (29 笔交易)：
- trend_up_20250612：2 (7%)
- trend_up_20250715：2 (7%)
- trend_up_20250722：2 (7%)
- trend_up_20250723：2 (7%)
- trend_up_20250724：2 (7%)
- trend_up_20250914：2 (7%)
- trend_up_20260115：2 (7%)
- trend_up_20260418：2 (7%)
- trend_up_20250611：1 (3%)
- trend_up_20250728：1 (3%)
- trend_up_20250729：1 (3%)
- trend_up_20250730：1 (3%)
- trend_up_20250811：1 (3%)
- trend_up_20250814：1 (3%)
- trend_up_20250819：1 (3%)
- trend_up_20260116：1 (3%)
- trend_up_20260409：1 (3%)
- trend_up_20260416：1 (3%)
- trend_up_20260417：1 (3%)
- trend_up_20260419：1 (3%)
- trend_up_20260423：1 (3%)

**ATR_ETH_3m** @ range (75 笔交易)：
- range_W36_2025：5 (7%)
- range_W01_2026：5 (7%)
- range_W02_2026：5 (7%)
- range_W27_2025：4 (5%)
- range_W50_2025：4 (5%)
- range_W18_2026：4 (5%)
- range_W24_2025：3 (4%)
- range_W25_2025：3 (4%)
- range_W26_2025：3 (4%)
- range_W39_2025：3 (4%)
- range_W40_2025：3 (4%)
- range_W04_2026：3 (4%)
- range_W14_2026：3 (4%)
- range_W38_2025：2 (3%)
- range_W41_2025：2 (3%)
- range_W43_2025：2 (3%)
- range_W44_2025：2 (3%)
- range_W49_2025：2 (3%)
- range_W03_2026：2 (3%)
- range_W11_2026：2 (3%)
- range_W13_2026：2 (3%)
- range_W16_2026：2 (3%)
- range_W35_2025：1 (1%)
- range_W37_2025：1 (1%)
- range_W42_2025：1 (1%)
- range_W51_2025：1 (1%)
- range_W05_2026：1 (1%)
- range_W12_2026：1 (1%)
- range_W15_2026：1 (1%)
- range_W17_2026：1 (1%)
- range_W19_2026：1 (1%)

**BAW_ETH_5m** @ trend_down (56 笔交易)：
- trend_down_20260224：3 (5%)
- trend_down_20251024：2 (4%)
- trend_down_20251112：2 (4%)
- trend_down_20251113：2 (4%)
- trend_down_20251124：2 (4%)
- trend_down_20251217：2 (4%)
- trend_down_20260301：2 (4%)
- trend_down_20250622：1 (2%)
- trend_down_20250623：1 (2%)
- trend_down_20250923：1 (2%)
- trend_down_20250927：1 (2%)
- trend_down_20251011：1 (2%)
- trend_down_20251012：1 (2%)
- trend_down_20251021：1 (2%)
- trend_down_20251023：1 (2%)
- trend_down_20251103：1 (2%)
- trend_down_20251107：1 (2%)
- trend_down_20251109：1 (2%)
- trend_down_20251111：1 (2%)
- trend_down_20251116：1 (2%)
- trend_down_20251117：1 (2%)
- trend_down_20251118：1 (2%)
- trend_down_20251121：1 (2%)
- trend_down_20251123：1 (2%)
- trend_down_20251125：1 (2%)
- trend_down_20251126：1 (2%)
- trend_down_20251129：1 (2%)
- trend_down_20251202：1 (2%)
- trend_down_20251205：1 (2%)
- trend_down_20251216：1 (2%)
- trend_down_20251218：1 (2%)
- trend_down_20260122：1 (2%)
- trend_down_20260126：1 (2%)
- trend_down_20260130：1 (2%)
- trend_down_20260203：1 (2%)
- trend_down_20260205：1 (2%)
- trend_down_20260207：1 (2%)
- trend_down_20260209：1 (2%)
- trend_down_20260210：1 (2%)
- trend_down_20260211：1 (2%)
- trend_down_20260217：1 (2%)
- trend_down_20260218：1 (2%)
- trend_down_20260219：1 (2%)
- trend_down_20260221：1 (2%)
- trend_down_20260227：1 (2%)
- trend_down_20260302：1 (2%)
- trend_down_20260307：1 (2%)
- trend_down_20260308：1 (2%)

**BTP_ETH_30m** @ trend_down (44 笔交易)：
- trend_down_20260126：3 (7%)
- trend_down_20251018：2 (5%)
- trend_down_20251023：2 (5%)
- trend_down_20251109：2 (5%)
- trend_down_20260207：2 (5%)
- trend_down_20260208：2 (5%)
- trend_down_20260214：2 (5%)
- trend_down_20260221：2 (5%)
- trend_down_20250623：1 (2%)
- trend_down_20250926：1 (2%)
- trend_down_20250927：1 (2%)
- trend_down_20251019：1 (2%)
- trend_down_20251031：1 (2%)
- trend_down_20251105：1 (2%)
- trend_down_20251107：1 (2%)
- trend_down_20251111：1 (2%)
- trend_down_20251115：1 (2%)
- trend_down_20251116：1 (2%)
- trend_down_20251117：1 (2%)
- trend_down_20251118：1 (2%)
- trend_down_20251122：1 (2%)
- trend_down_20251123：1 (2%)
- trend_down_20251125：1 (2%)
- trend_down_20251126：1 (2%)
- trend_down_20251218：1 (2%)
- trend_down_20251219：1 (2%)
- trend_down_20260123：1 (2%)
- trend_down_20260202：1 (2%)
- trend_down_20260206：1 (2%)
- trend_down_20260209：1 (2%)
- trend_down_20260212：1 (2%)
- trend_down_20260213：1 (2%)
- trend_down_20260218：1 (2%)
- trend_down_20260225：1 (2%)
- trend_down_20260309：1 (2%)

**BTP_ETH_30m** @ range (49 笔交易)：
- range_W40_2025：5 (10%)
- range_W42_2025：4 (8%)
- range_W51_2025：4 (8%)
- range_W17_2026：4 (8%)
- range_W27_2025：3 (6%)
- range_W43_2025：3 (6%)
- range_W02_2026：3 (6%)
- range_W14_2026：3 (6%)
- range_W26_2025：2 (4%)
- range_W38_2025：2 (4%)
- range_W41_2025：2 (4%)
- range_W44_2025：2 (4%)
- range_W52_2025：2 (4%)
- range_W03_2026：2 (4%)
- range_W05_2026：2 (4%)
- range_W15_2026：2 (4%)
- range_W28_2025：1 (2%)
- range_W01_2026：1 (2%)
- range_W04_2026：1 (2%)
- range_W13_2026：1 (2%)

**ATR_ETH_3m** @ trend_down (36 笔交易)：
- trend_down_20260223：2 (6%)
- trend_down_20260329：2 (6%)
- trend_down_20250925：1 (3%)
- trend_down_20251010：1 (3%)
- trend_down_20251016：1 (3%)
- trend_down_20251023：1 (3%)
- trend_down_20251031：1 (3%)
- trend_down_20251104：1 (3%)
- trend_down_20251106：1 (3%)
- trend_down_20251108：1 (3%)
- trend_down_20251115：1 (3%)
- trend_down_20251119：1 (3%)
- trend_down_20251120：1 (3%)
- trend_down_20251123：1 (3%)
- trend_down_20251125：1 (3%)
- trend_down_20251126：1 (3%)
- trend_down_20251201：1 (3%)
- trend_down_20251202：1 (3%)
- trend_down_20251215：1 (3%)
- trend_down_20251217：1 (3%)
- trend_down_20260123：1 (3%)
- trend_down_20260126：1 (3%)
- trend_down_20260130：1 (3%)
- trend_down_20260201：1 (3%)
- trend_down_20260203：1 (3%)
- trend_down_20260204：1 (3%)
- trend_down_20260211：1 (3%)
- trend_down_20260213：1 (3%)
- trend_down_20260217：1 (3%)
- trend_down_20260220：1 (3%)
- trend_down_20260221：1 (3%)
- trend_down_20260226：1 (3%)
- trend_down_20260307：1 (3%)
- trend_down_20260327：1 (3%)

**BTP_BTC_1H** @ trend_down (18 笔交易)：
- trend_down_20251218：2 (11%)
- trend_down_20251019：1 (6%)
- trend_down_20251105：1 (6%)
- trend_down_20251118：1 (6%)
- trend_down_20251120：1 (6%)
- trend_down_20251123：1 (6%)
- trend_down_20251126：1 (6%)
- trend_down_20251128：1 (6%)
- trend_down_20251216：1 (6%)
- trend_down_20260202：1 (6%)
- trend_down_20260206：1 (6%)
- trend_down_20260212：1 (6%)
- trend_down_20260213：1 (6%)
- trend_down_20260214：1 (6%)
- trend_down_20260215：1 (6%)
- trend_down_20260218：1 (6%)
- trend_down_20260227：1 (6%)

## 分层 Regime 字段分布

以下展示每个 regime 内部的分层标签混合程度。
如果某个 regime 内状态过于混杂，说明该 regime 定义可能需要细化。

### regime = **range** (224 笔交易)

- **structure_state：** range (224, 100%)
- **volatility_state：** low (83, 37%) / medium (76, 34%) / high (65, 29%)
- **orderflow_state：** unknown (133, 59%) / bullish (87, 39%) / neutral (3, 1%) / bearish (1, 0%)
- **macro_state：** neutral (135, 60%) / flow_driven (88, 39%) / event_risk (1, 0%)

### regime = **trend_down** (154 笔交易)

- **structure_state：** trend_down (154, 100%)
- **volatility_state：** low (74, 48%) / high (49, 32%) / medium (31, 20%)
- **orderflow_state：** unknown (86, 56%) / bullish (68, 44%)
- **macro_state：** neutral (87, 56%) / flow_driven (67, 44%)

### regime = **trend_up** (138 笔交易)

- **structure_state：** trend_up (138, 100%)
- **volatility_state：** high (71, 51%) / medium (35, 25%) / low (32, 23%)
- **orderflow_state：** unknown (108, 78%) / bullish (30, 22%)
- **macro_state：** neutral (110, 80%) / flow_driven (28, 20%)

## Market Opportunity Score
v1.1 中 Market Opportunity Score 为 placeholder，默认值 1.0。
Final Activation Score = Enable Score × 1.0

## Regime 表现详情
| strategy_name | regime | trade_count | win_rate | avg_R | profit_factor | max_drawdown_R | payoff_ratio | longest_losing_streak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAW_ETH_5m | range | 80 | 0.50 | 0.10 | 1.12 | -14.87 | 1.12 | 5 |
| BAW_ETH_5m | trend_up | 69 | 0.43 | -0.05 | 0.93 | -14.25 | 1.21 | 6 |
| ATR_ETH_3m | trend_up | 33 | 0.52 | 0.47 | 2.77 | -1.96 | 2.61 | 3 |
| BTP_BTC_1H | trend_up | 7 | 0.71 | 0.02 | 1.08 | -1.06 | 0.43 | 1 |
| BTP_BTC_1H | range | 20 | 0.60 | -0.04 | 0.89 | -2.09 | 0.59 | 2 |
| BTP_ETH_30m | trend_up | 29 | 0.52 | -0.07 | 0.85 | -3.93 | 0.79 | 4 |
| ATR_ETH_3m | range | 75 | 0.40 | 0.14 | 1.30 | -4.64 | 1.94 | 6 |
| BAW_ETH_5m | trend_down | 56 | 0.61 | 0.56 | 2.02 | -6.94 | 1.31 | 3 |
| BTP_ETH_30m | trend_down | 44 | 0.73 | 0.22 | 1.83 | -4.19 | 0.69 | 4 |
| BTP_ETH_30m | range | 49 | 0.63 | 0.00 | 1.00 | -4.49 | 0.58 | 3 |
| ATR_ETH_3m | trend_down | 36 | 0.56 | 0.33 | 1.94 | -2.75 | 1.55 | 3 |
| BTP_BTC_1H | trend_down | 18 | 0.72 | 0.23 | 1.97 | -1.34 | 0.76 | 2 |

## Monte Carlo 风险验证摘要
| strategy_name | regime | median_total_R | p5_total_R | p95_max_drawdown_R | probability_of_negative_total_R | probability_drawdown_exceeds_threshold |
| --- | --- | --- | --- | --- | --- | --- |
| BAW_ETH_5m | range | 7.75 | -21.31 | -8.15 | 33.68% | 85.72% |
| BAW_ETH_5m | trend_up | -3.53 | -25.71 | -7.37 | 60.22% | 81.54% |
| ATR_ETH_3m | trend_up | 15.41 | 4.56 | -1.40 | 0.90% | 0.06% |
| BTP_BTC_1H | trend_up | 0.24 | -3.00 | 0.00 | 43.54% | 0.00% |
| BTP_BTC_1H | range | -0.70 | -6.18 | -1.21 | 58.82% | 0.56% |
| BTP_ETH_30m | trend_up | -2.26 | -10.99 | -2.81 | 65.00% | 15.14% |
| ATR_ETH_3m | range | 10.07 | -7.65 | -4.15 | 16.84% | 26.16% |
| BAW_ETH_5m | trend_down | 31.09 | 6.08 | -3.82 | 2.04% | 26.54% |
| BTP_ETH_30m | trend_down | 9.87 | 0.87 | -1.61 | 3.62% | 0.12% |
| BTP_ETH_30m | range | 0.13 | -9.53 | -2.62 | 48.60% | 11.06% |
| ATR_ETH_3m | trend_down | 11.97 | 0.02 | -1.95 | 4.98% | 1.02% |
| BTP_BTC_1H | trend_down | 4.20 | -1.64 | -1.06 | 11.68% | 0.02% |

## Time Under Water / Recovery 风险

Time Under Water Ratio 衡量策略在亏损回补中煎熬的时间比例；
Recovery Trades 衡量从回撤到重新创新高所经历的笔数。

### ⚠️ 高 TUW 组合（TUW > 50%，共 10 个）

- **BAW_ETH_5m** @ trend_up — TUW=89.9%, max_recovery=3笔, avg_recovery=2.0笔
- **BAW_ETH_5m** @ range — TUW=87.5%, max_recovery=5笔, avg_recovery=3.7笔
- **BTP_ETH_30m** @ range — TUW=85.7%, max_recovery=16笔, avg_recovery=8.8笔
- **ATR_ETH_3m** @ range — TUW=84.0%, max_recovery=34笔, avg_recovery=7.9笔
- **BTP_ETH_30m** @ trend_up — TUW=82.8%, max_recovery=17笔, avg_recovery=5.0笔 (样本少，参考有限)
- **BTP_BTC_1H** @ range — TUW=80.0%, max_recovery=8笔, avg_recovery=5.5笔 (样本少，参考有限)
- **BAW_ETH_5m** @ trend_down — TUW=62.5%, max_recovery=12笔, avg_recovery=4.4笔
- **ATR_ETH_3m** @ trend_down — TUW=61.1%, max_recovery=6笔, avg_recovery=3.3笔
- **BTP_ETH_30m** @ trend_down — TUW=56.8%, max_recovery=18笔, avg_recovery=8.0笔
- **ATR_ETH_3m** @ trend_up — TUW=54.5%, max_recovery=7笔, avg_recovery=2.2笔

### 🐢 恢复缓慢组合（max_recovery > 20笔，共 1 个）

- **ATR_ETH_3m** @ range — 最长恢复需 34 笔交易

### 完整 TUW / Recovery 一览

| strategy_name | regime | trade_count | time_under_water_ratio | max_recovery_trades | average_recovery_trades |
| --- | --- | --- | --- | --- | --- |
| BAW_ETH_5m | trend_up | 69 | 89.9% | 3 | 2.0 |
| BAW_ETH_5m | range | 80 | 87.5% | 5 | 3.7 |
| BTP_ETH_30m | range | 49 | 85.7% | 16 | 8.8 |
| ATR_ETH_3m | range | 75 | 84.0% | 34 | 7.9 |
| BTP_ETH_30m | trend_up | 29 | 82.8% | 17 | 5.0 |
| BTP_BTC_1H | range | 20 | 80.0% | 8 | 5.5 |
| BAW_ETH_5m | trend_down | 56 | 62.5% | 12 | 4.4 |
| ATR_ETH_3m | trend_down | 36 | 61.1% | 6 | 3.3 |
| BTP_ETH_30m | trend_down | 44 | 56.8% | 18 | 8.0 |
| ATR_ETH_3m | trend_up | 33 | 54.5% | 7 | 2.2 |
| BTP_BTC_1H | trend_down | 18 | 50.0% | 7 | 4.5 |
| BTP_BTC_1H | trend_up | 7 | 28.6% | N/A | N/A |

---

### 风险分类说明
| 分类 | 判断标准 | 含义 |
|------|---------|------|
| **样本不足** | trade_count < min_trades | 当前数据不足以做出可靠结论 |
| **策略可能失效** | Base Score 低（长期指标恶化，负期望值、PF<1） | 策略在当前 regime 下可能不再有效 |
| **市场暂时无机会** | Recent Health 低但 Regime Edge 仍高 | 近期表现差可能是市场环境问题，非策略失效 |
| **极端盈利依赖** | Edge Concentration Warning 触发 | 收益过度依赖少数极端交易，稳定性存疑 |
| **MC 尾部风险过高** | 模拟路径中高概率出现大幅回撤 | 即使长期 edge 存在，尾部风险不可接受 |

*Generated by Strategy Enable Score System v1.1*