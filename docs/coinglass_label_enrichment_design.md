# CoinGlass 数据接入与标签回填设计文档

**版本：** v1.0  
**创建时间：** 2026-05-13  
**状态：** 设计文档，不含实现代码  
**依赖：** P2-5 已完成，Readiness: BLOCK（orderflow_state / macro_state 100% unknown）

---

## 1. 当前问题

### P2-5 Readiness 结论

| Feature | Readiness | 阻断字段 |
|---------|-----------|---------|
| Automatic Regime Classifier | **BLOCK** | orderflow_state, macro_state |
| Market Opportunity Score | **BLOCK** | orderflow_state, macro_state |
| Layered Regime Analysis | **BLOCK** | orderflow_state, macro_state |

### 字段状态

| 字段 | Quality Score | Status |
|------|--------------|--------|
| session | 100 | PASS |
| structure_state | 100 | PASS |
| volatility_state | 100 | PASS |
| **orderflow_state** | **0** | **BLOCK** |
| **macro_state** | **0** | **BLOCK** |
| oi_state | N/A (不在监测列表) | — |
| funding_state | N/A | — |
| etf_flow_state | N/A | — |
| coinbase_premium_state | N/A | — |

### 核心矛盾

P2-5 的 readiness 判断明确指出：**classifier 和 Market Opportunity Score 暂不应实现**，因为 `orderflow_state` 和 `macro_state` 两个关键字段 100% unknown。

用户已有 CoinGlass API，应利用外部市场数据回填这些字段，解除 BLOCK。

---

## 2. CoinGlass 数据源分层

### A. Futures / Orderflow 类

**用途：** 回填 `orderflow_state`、`oi_state`、`funding_state`

| 数据端点 | 原始指标 | 最小粒度 | 适用交易对 |
|---------|---------|---------|-----------|
| Open Interest History | OI 绝对值 + OI 变化 | 5m/15m/1h/4h | BTC, ETH |
| Funding Rate History | Funding Rate % | 1h/4h/8h | BTC, ETH |
| Taker Buy/Sell Volume | 主动买卖成交量 | 5m/15m/1h | BTC, ETH |
| Long/Short Ratio | 多空持仓比 | 5m/15m/1h/4h | BTC, ETH |
| Liquidation Data | 清算量/清算价格 | 5m/15m/1h | BTC, ETH |
| Futures Market Overview | 综合期货数据 | 1h/4h | BTC, ETH |

> **说明：** CoinGlass 主要覆盖 BTC 和 ETH 的 USDⓈ-M 期货数据。如果未来需要其他交易对（如 SOL），需确认 API 覆盖范围。

### B. ETF / Macro Crypto Flow 类

**用途：** 回填 `etf_flow_state`、`macro_state`

| 数据端点 | 原始指标 | 最小粒度 | 说明 |
|---------|---------|---------|------|
| Bitcoin ETF Flow | BTC ETF 日净流量（USD） | 日 | 适用于日级 macro_state |
| Ethereum ETF Flow | ETH ETF 日净流量（USD） | 日 | 同上 |
| Economic Calendar | 高影响事件列表 | 事件驱动 | 人工辅助打标签 |
| Crypto News | 重大事件（ETF审批、监管等） | 事件驱动 | **不直接自动打标签** |

> **注意：** ETF 流量数据通常为日级（T+1 延迟）。对于 5m/30m/1H 级别的策略，ETF 日级数据只能作为当日宏观背景，不能用于精准 timing。

### C. Volatility / Market Condition 类

**用途：** 回填或验证 `volatility_state`、辅助 Market Opportunity Score

| 数据端点 | 原始指标 | 用途 |
|---------|---------|------|
| Futures Indicators | 多维度期货指标 | 验证 volatility_state |
| Spot Indicators | 现货市场指标 | 辅助 regime 判断 |
| Liquidation Intensity | 清算强度 | 极端行情识别 |

> **说明：** `volatility_state` 当前已由上游从 OHLCV 回填，PASS。CoinGlass 数据可作为交叉验证，非 P2 必做。

---

## 3. 字段映射设计

| 目标字段 | CoinGlass 数据源 | 原始指标 | 建议标签值 | 计算窗口 | P2 必做 |
|---------|-----------------|---------|-----------|---------|--------|
| `orderflow_state` | Taker Buy/Sell Volume + OI | Taker imbalance + OI delta | `futures_led_up`, `futures_led_down`, `spot_led`, `distribution`, `absorption`, `neutral` | 4h / 1h | ✅ |
| `macro_state` | ETF Flow + Economic Calendar | ETF net flow + event flags | `ETF_inflow`, `ETF_outflow`, `event_risk`, `neutral` | 日 | ✅ |
| `volatility_state` | Futures Indicators（验证） | 当前已由 OHLCV 回填 | `low`, `medium`, `high` | — | ❌ P2 不做 |
| `oi_state` | Open Interest History | OI change % | `rising`, `falling`, `flat` | 4h / 1h | ✅ |
| `funding_state` | Funding Rate History | Funding rate % | `positive`, `negative`, `neutral` | 4h / 1h | ✅ |
| `etf_flow_state` | BTC/ETH ETF Flow | Net flow USD | `inflow`, `outflow`, `neutral` | 日 | ✅ |
| `coinbase_premium_state` | **CoinGlass 不可靠提供** | CBP Index (非 CoinGlass) | `positive`, `negative`, `neutral` | 1h / 4h | ❌ 外部数据源待定 |

### coinbase_premium_state 处理

CoinGlass **不直接提供 Coinbase Premium Index**。CBP 数据需要从以下来源获取：

1. **SisieAssistant CBP 数据**（已有）：`sisie-assistant` 项目的 CBP 数据可直接用于回填
2. **CryptoQuant / Glassnode**：提供 exchanges flow 数据
3. **自计算**：Binance BTCUSDT vs Coinbase BTCUSD 价差

**建议：** 将 `coinbase_premium_state` 标记为「外部数据源待定」，不纳入第一批 P2 CoinGlass 回填范围。

---

## 4. 最小可行 P2 实现范围

### 第一批做（P2-7 + P2-8）

| 目标字段 | 数据源 | 理由 |
|---------|--------|------|
| `oi_state` | CoinGlass OI History | 数据稳定、粒度好、计算简单 |
| `funding_state` | CoinGlass Funding Rate | 数据稳定、值域明确 |
| `orderflow_state` | CoinGlass Taker Buy/Sell + OI | 解除 classifier BLOCK 的**核心字段** |
| `etf_flow_state` | CoinGlass BTC/ETH ETF Flow | 数据稳定、日级即可 |
| `macro_state` | ETF Flow + 经济日历 | 解除 classifier BLOCK 的**核心字段** |

### 第一批不做

| 不做的内容 | 理由 |
|-----------|------|
| 自动 regime classifier | 设计文档 §1 明确：当前 readiness = BLOCK，先回填标签再实现 |
| Market Opportunity Score | 同上 |
| 实时启停提醒 | P2 范围外，属于 P3 在线系统 |
| Dashboard | P2 范围外 |
| volatility_state 重算 | 已由 OHLCV 回填，PASS |
| coinbase_premium_state | CoinGlass 不直接提供 |
| 5m 级别的精细 orderflow 标签 | CoinGlass 大部分端点最小粒度 5m，但 ETF/宏观是日级 |

---

## 5. 标签生成规则草案

> 所有阈值必须写入 `config.yaml`，不要写死。以下 `X` 为可配置阈值。

### 5.1 `oi_state`

```
计算：OI_change_pct = (current_OI - prev_OI) / prev_OI

if OI_change_pct > +oi_change_pct_rising:    → "rising"
elif OI_change_pct < -oi_change_pct_falling: → "falling"
else:                                        → "flat"
```

默认阈值：`oi_change_pct_rising = 0.03`, `oi_change_pct_falling = -0.03`

对齐窗口：按 period（4h 或 1h）计算 OI 变化

### 5.2 `funding_state`

```
计算：funding_rate = 最近一个 funding period 的利率

if funding_rate > +funding_positive:  → "positive"
elif funding_rate < +funding_negative: → "negative"
else:                                  → "neutral"
```

默认阈值：`funding_positive = 0.0001` (0.01%), `funding_negative = -0.0001`

对齐方式：取 `entry_time` 之前最近完成的 funding interval

### 5.3 `orderflow_state`

多信号融合规则：

```
1. 计算 Taker Imbalance:
   taker_imbalance = (taker_buy_vol - taker_sell_vol) / total_vol

2. 计算 OI + Price 联动:
   price_change = (current_price - prev_price) / prev_price

3. 综合判断 (优先级从高到低):
   if taker_imbalance > +taker_imbalance_bullish:
       → "futures_led" if OI 变化匹配价格方向, else "spot_led"
   elif taker_imbalance < taker_imbalance_bearish:
       → "futures_led" if OI 变化匹配价格方向, else "distribution"
   elif OI_rising and price_rising:   → "futures_led_up"
   elif OI_rising and price_falling:  → "futures_led_down"
   elif OI_flat and volume_spike:     → "absorption" 或 "distribution"
   else:                              → "neutral"
```

默认阈值：`taker_imbalance_bullish = 0.10`, `taker_imbalance_bearish = -0.10`

对齐窗口：4h（与 regime 主分组周期一致）

> **警告：** `orderflow_state` 是设计文档 §3.4 定义的最复杂标签。第一版建议只区分 `futures_led` / `spot_led` / `neutral` 三种状态，避免过度推断。

### 5.4 `etf_flow_state`

```
计算：ETF_net_flow = 当日 BTC ETF + ETH ETF 净流量 (USD)

if ETF_net_flow > +etf_flow_inflow_usd:   → "inflow"
elif ETF_net_flow < etf_flow_outflow_usd: → "outflow"
else:                                     → "neutral"
```

默认阈值：`etf_flow_inflow_usd = 50_000_000` (5000万美元), `etf_flow_outflow_usd = -50_000_000`

对齐方式：日级，取 `entry_time` 所在日期的 ETF 流量数据

### 5.5 `macro_state`

```
事件检测:
if entry_time 在高影响经济事件窗口（±2h）: → "event_risk"

ETF 异常检测:
elif ETF_net_flow > +etf_flow_inflow_usd:   → "ETF_inflow"
elif ETF_net_flow < etf_flow_outflow_usd:   → "ETF_outflow"

默认:
→ "neutral"
```

事件列表来源：经济日历 API（非 CoinGlass，需从 `sisie-assistant` 的经济日历模块获取或单独接入）

> **注意：** `macro_state` 第一版只做「事件型占位判断」——即只在有明确高影响事件时标记 `event_risk`，其余时间标记 `neutral` 或基于 ETF 流量判断。不做复杂的 NLP 新闻分析。

---

## 6. 数据时间对齐原则

### 6.1 核心规则

```
交易记录的 entry_time 是所有标签对齐的主时间轴
外部数据需要按 symbol + time_bucket 对齐到 entry_time
```

### 6.2 粒度对齐

| CoinGlass 数据粒度 | 标签对齐方式 |
|-------------------|------------|
| 5m / 15m / 1h | 取 `entry_time` 之前最近完成的 candle |
| 4h | 取 `entry_time` 所在 4h 区间的前一个已完成区间 |
| 日级 | 当日全部交易共享同一日级标签 |
| 事件驱动 | 以事件窗口覆盖判断 |

### 6.3 Lookahead Bias 防范

**严禁规则：**

```
❌ 不允许：entry_time = 10:00，使用 10:30 的 OI 数据
❌ 不允许：entry_time = 周一，使用周二的 ETF 流量
❌ 不允许：用已知的 future liquidation 判断当前 orderflow
```

**正确做法：**

```
✅ entry_time = 10:00，使用 09:00–09:59 的已完成 1h candle 数据
✅ entry_time = 周一，使用上周五的 ETF 流量（T+1 延迟接受）
✅ 所有标签基于 entry_time 之前已闭合的数据区间
```

### 6.4 数据缺失处理

```
if 外部数据在 entry_time 对应区间无数据:
    → 向前回溯最近一个可用数据点
    → 回溯最多 max_lookback_intervals 个区间
    → 仍无数据 → 标签填 "unknown"
```

配置：`max_lookback_intervals = 4`

---

## 7. 缓存与审计设计

### 7.1 文件结构

```
data/external/coinglass/
  raw/                              ← 原始 API 响应（JSON）
    oi_history_BTC_2026-01-01.json
    funding_rate_ETH_2026-01-01.json
    etf_flow_BTC_2026-01-01.json
    ...
  processed/                        ← 处理后时间序列（parquet/csv）
    oi_btc_4h.parquet
    funding_eth_4h.parquet
    taker_volume_btc_4h.parquet
    etf_flow_daily.parquet
    ...

outputs/data_quality/
  enriched_trades.csv               ← 回填后的 CSV（新文件）
  enrichment_audit_report.md        ← 回填审计报告
```

### 7.2 审计要求

- **原始 API 响应保存为 raw**，保留完整 JSON，文件名含日期范围
- **处理后的时间序列保存为 processed**，包含数据源、时间戳、symbol、原始值
- **回填后的 cleaned CSV 另存为新文件** `enriched_trades.csv`，不覆盖 `cleaned_trades.csv`
- **每个被回填字段保留 `original_*` 列**，如 `original_orderflow_state`
- **审计报告记录**：
  - 每个字段回填了多少行
  - 多少行因数据缺失仍为 unknown
  - 每行使用的数据源和区间
  - 时间对齐 audit trail

---

## 8. 配置设计

以下配置段将添加到 `config.yaml`（未来实现时）：

```yaml
coinglass:
  enabled: false
  api_key_env: "COINGLASS_API_KEY"
  cache_dir: "data/external/coinglass"
  symbols:
    - BTC
    - ETH
  rate_limit_per_minute: 30
  lookback_days: 365

label_enrichment:
  enabled: false
  input_path: "outputs/data_quality/cleaned_trades.csv"
  output_path: "outputs/data_quality/enriched_trades.csv"
  preserve_original_columns: true
  alignment:
    time_field: "entry_time"
    prevent_lookahead: true
    max_lookback_intervals: 4
  thresholds:
    oi_change_pct_rising: 0.03
    oi_change_pct_falling: -0.03
    taker_imbalance_bullish: 0.10
    taker_imbalance_bearish: -0.10
    funding_positive: 0.0001
    funding_negative: -0.0001
    etf_flow_inflow_usd: 50000000
    etf_flow_outflow_usd: -50000000
  orderflow_mode: "simplified"  # "simplified" | "full"
```

### 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `coinglass.api_key_env` | `COINGLASS_API_KEY` | API key 从环境变量读取 |
| `coinglass.rate_limit_per_minute` | 30 | CoinGlass 免费 API 约 30 req/min |
| `label_enrichment.orderflow_mode` | `simplified` | `simplified` = futures_led/spot_led/neutral；`full` = 全部 6 种状态 |
| `label_enrichment.alignment.prevent_lookahead` | true | 必须为 true，防止未来信息泄露 |
| `label_enrichment.alignment.max_lookback_intervals` | 4 | 向前回溯的最大区间数 |

---

## 9. 开发阶段拆分

### P2-7：CoinGlass Fetch/Cache Layer

| 项目 | 内容 |
|------|------|
| **目标** | 搭建 CoinGlass API 数据抓取和本地缓存层 |
| **输入** | `config.yaml` coinglass 段，API key |
| **输出** | `data/external/coinglass/raw/` + `data/external/coinglass/processed/` |
| **验收标准** | - OI history / funding rate / taker volume / ETF flow 四个端点可拉取<br>- 支持 BTC + ETH<br>- 缓存命中时不重复请求<br>- rate limit 控制不报 429<br>- 处理后的 parquet 文件按 symbol + interval 可查询 |
| **风险点** | - API key 配额不足<br>- 历史数据覆盖范围不完整<br>- 网络超时<br>- 数据格式变化 |

### P2-8：Label Enrichment Engine

| 项目 | 内容 |
|------|------|
| **目标** | 实现标签回填引擎 |
| **输入** | `cleaned_trades.csv` + `processed/*.parquet` |
| **输出** | `enriched_trades.csv` + `enrichment_audit_report.md` |
| **验收标准** | - orderflow_state / oi_state / funding_state / etf_flow_state / macro_state 回填成功<br>- 回填率 ≥ 80%（CoinGlass 数据覆盖范围内的交易）<br>- lookahead bias 检测测试通过<br>- 原始值保留到 original_* 列<br>- 不改变 pnl_R / trade_id / strategy_name / regime |
| **风险点** | - 时间对齐逻辑复杂（多种粒度混用）<br>- orderflow_state 简化版可能过于粗糙<br>- 日级标签可能不适合高频策略<br>- 某些交易对 CoinGlass 不覆盖 |

### P2-9：Enriched Data Regression + Readiness Re-Check

| 项目 | 内容 |
|------|------|
| **目标** | 用 enriched CSV 跑评分回归，重新评估 readiness |
| **输入** | `enriched_trades.csv` |
| **输出** | `outputs/validation_enriched/` + `enriched_data_regression_report.md` |
| **验收标准** | - 与 baseline 的 Enable Score delta = 0<br>- 重新运行 label_quality → readiness 不再 BLOCK（预期至少升为 WARN 或 PASS）<br>- 标签质量分数报告更新<br>- 109 tests 仍然通过 |
| **风险点** | - 回填率不够 → readiness 仍为 BLOCK<br>- 标签值不准确 → 不影响评分但会误导后续 classifier |

### P2-10（Optional）：Market Opportunity Score Prototype

| 项目 | 内容 |
|------|------|
| **目标** | 实现 Market Opportunity Score 第一版原型 |
| **输入** | enriched trades + 外部市场数据 |
| **输出** | enable_score.csv 中 market_opportunity_score 不再为 1.0 |
| **验收标准** | - 基于 orderflow / OI / funding / macro 的市场机会评分<br>- 不改变 Enable Score 公式<br>- Final Activation Score = Enable Score × Market Opportunity Score |
| **风险点** | - Market Opportunity Score 定义主观性强<br>- 回测中难以验证市场机会评分准确性<br>- 不建议在真实交易日志不足时启用 |

---

## 10. 风险提示

| # | 风险 | 影响 | 缓解措施 |
|---|------|------|---------|
| R1 | CoinGlass API 数据覆盖范围不完整（可能不含某些小币种） | 部分交易对标签无法回填 | 当前默认只覆盖 BTC/ETH，对应 SSS 中 BTP_BTC_1H 和 ETH 三策略 |
| R2 | 不同 endpoint 时间粒度不同（5m OI vs 日级 ETF） | 混合粒度标签不一致 | 用 alignment 配置明确每字段的时间粒度；报告中注明粒度差异 |
| R3 | ETF / macro 数据是日级，不适合给 5m 策略打精细标签 | BAW_ETH_5m 的日级 macro_state 可能不反映实时的市场情绪 | 日级标签仅作为背景，不入 Enable Score；在报告中标注 |
| R4 | orderflow_state 不能只靠单一指标（Taker imbalance 可能受洗盘交易影响） | 标签质量不可靠 | 第一版多信号融合（§5.3）；简化模式只区分 3 种状态 |
| R5 | **Lookahead Bias** — 使用 entry_time 之后产生的数据 | 回测结果虚假乐观 | 强制 `prevent_lookahead: true`；测试验证；永远取已完成区间 |
| R6 | 第一次实现只做标签补全，不改变 Enable Score | 如果用户误以为标签回填会改变评分 | 在报告中明确声明 |
| R7 | CoinGlass API 免费版有 rate limit 和端点限制 | 大跨度历史数据抓取时间很长 | 缓存设计（§7）；先拉日级数据再按需拉细粒度 |
| R8 | coinbase_premium_state 需要外部数据源（CoinGlass 不提供） | 该字段暂时无法回填 | 标记为「外部数据源待定」；从 SisieAssistant CBP 数据获取 |

---

## 11. 附录：与现有系统集成点

```
data/combined_trade_log_20260513.csv  ← 原始真实 CSV
        ↓ P2-2 label_quality
outputs/data_quality/cleaned_trades.csv  ← 当前默认输入
        ↓ P2-8 label enrichment (未来)
outputs/data_quality/enriched_trades.csv  ← 回填后输入
        ↓ main.py
outputs/*.csv / summary_report.md  ← 评分输出（不变）
```

- **不修改** `main.py` pipeline
- **不修改** 任何评分公式
- **不覆盖** 现有 `cleaned_trades.csv`
- **保留** 所有 `original_*` 审计列
- **新增** 可独立运行的 `label_enrichment.py` 模块

---

*Document version 1.0 — for review before P2-7 implementation*
