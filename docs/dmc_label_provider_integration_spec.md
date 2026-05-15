# DMC Label Provider Integration Specification

**版本：** v1.0  
**日期：** 2026-05-15  
**涉及项目：** SSS-Strategy-Score-System v1.1.0 / DMC-Sisie-Quantive  
**状态：** 设计文档 — 待实施

---

## 1. 目标与职责边界

### 目标

定义一个稳定的接口，让 DMC-Sisie-Quantive（本地回测引擎）可以为 SSS-Strategy-Score-System（策略启用评分系统）提供以下结构标签回填：

1. `session`
2. `regime`
3. `regime_snapshot_id`
4. `structure_state`
5. `volatility_state`
6. `setup_type`（如果 DMC 能可靠提供）

### 职责边界

| 职责 | SSS | DMC |
|------|-----|-----|
| TradingView CSV → canonical CSV 转换 | ✅（`tradingview_converter.py`） | — |
| 4H parquet 数据读取 | — | ✅（已有，本地 `data/` 目录） |
| session 标签生成 | 内置规则（`label_quality.py`）也可以做 | ✅ `SessionEnricher`（已有，UTC 小时规则） |
| regime + regime_snapshot_id 标签生成 | — | ✅ `RegimeEnricher`（已有，4H EMA200） |
| structure_state 标签生成 | `label_quality.py`（复制自 regime）也可以做 | ✅ `StructureStateEnricher`（已有） |
| volatility_state 标签生成 | — | ✅ `VolatilityEnricher`（已有，4H ATR14百分位） |
| setup_type 标签生成 | — | ✅ `export_trade_log_csv()` 已有 `SETUP_TYPE_LABEL` |
| OI / Funding / CVD / Coinbase / ETF / Macro 标签 | ✅ `label_enrichment.py` (CoinGlass pipeline) | ❌ **不是 DMC 的职责** |
| Enable Score / 评分 / Monte Carlo | ✅ `main.py` | ❌ 不是 DMC 的职责 |
| classifier / Market Opp | ❌ 暂不实现 | ❌ 不是 DMC 的职责 |

---

## 2. 接口形式 — 第一版推荐

### 推荐：CLI CSV-in / CSV-out（方案 A）

| 属性 | 说明 |
|------|------|
| 形式 | SSS 调用 `dmc_bridge.py`（现有），bridge 内部调用 DMC enrichers |
| 输入 | SSS canonical CSV（`trade_id, strategy_name, symbol, direction, entry_time, exit_time, pnl_R, pnl_usd, ...`） |
| 输出 | 标注好的 CSV（所有字段 `__all__`，缺失填 `unknown`）+ audit report |
| 复杂度 | 低。SSS 不改架构，DMC 不改 TradeEnricher 接口 |
| 耦合度 | 松耦合。SSS 不直接 import DMC 内部模块，桥接层隔离依赖 |

### 为什么不选其他方案

| 方案 | 不建议原因 |
|------|-----------|
| B. Python adapter（SSS 直接 import DMC） | DMC 是 WSL 项目，SSS 是 Windows 项目；直接 import 需要 path hacks 和 pyarrow/fastparquet 依赖；当前 `dmc_bridge.py` 已实现但耦合度高 |
| C. HTTP API | 两个项目都在本地，不需要网络开销；增加运维复杂度（端口、auth） |

### 当前 dmc_bridge.py 状态

- `dmc_bridge.py` 已能直接调用 DMC 的 `SessionEnricher`、`RegimeEnricher`、`StructureStateEnricher`、`VolatilityEnricher`，生成 5 个标签字段
- 已在 `tradingview_converter.py` 中集成（`--apply-dmc-labels`）
- 5/5 tests passed
- **耦合点：** 通过 `importlib.util.spec_from_file_location` 动态加载 DMC 模块，需要 pyarrow/fastparquet 读取 4H parquet

### dmc_bridge.py 建议

**保留 `dmc_bridge.py` 作为 SSS 侧的 connector adapter**，但不强制所有用户使用。如果未来 DMC 路径有变，只需更新 `--dmc-root` 参数或 `symbol_4h_paths`。

**不做的事：**
- 不改名（当前职责清晰：SSS ↔ DMC bridge）
- 不重构（现有实现已验证可用）
- 不降级（DMC enrichers 比 SSS 内置 label_quality 提供更精确的 regime/volatility 标签）

---

## 3. 最小 Schema 定义

### 3.1 SSS 提供给 DMC 的最小输入

DMC bridge 从 SSS canonical CSV 读取以下列。最小输入只需 4 个核心列：

| 字段 | 类型 | 用途 |
|------|------|------|
| `entry_time` | ISO 8601 string | 所有标签的时间锚点；防 lookahead bias 的关键 |
| `direction` | string (`long` / `short`) | 确认开仓方向（DMC 个别 enricher 可能需要） |
| `symbol` | string (`BTCUSDT` / `ETHUSDT`) | 映射到对应 4H parquet 数据 |
| `strategy_name` | string | 映射 `setup_type`、策略元数据 |

DMC 不需要 `pnl_R`、`exit_time`、`pnl_usd` 等来生成标签，但 SSS 输出 CSV 中会保留这些列。

### 3.2 DMC 返回给 SSS 的最小输出

DMC 为每一行 **追加或覆盖** 以下列（以 dict 或 CSV 列形式返回）：

| 字段 | 类型 | 允许值 | 来源 Enricher | 缺失时的值 |
|------|------|--------|-------------|----------|
| `session` | str | `Asia` / `London` / `overlap` / `NY` / `weekend` / `unknown` | `SessionEnricher` | `unknown` |
| `regime` | str | `trend_up` / `trend_down` / `range` / `unknown` | `RegimeEnricher` | `unknown` |
| `regime_snapshot_id` | str | `{regime}_{YYYYMMDD}` / `{regime}_W{ww}_{yyyy}` / `{regime}_{YYYYMM}` / `unknown` | `RegimeEnricher` | `unknown` |
| `structure_state` | str | `trend_up` / `trend_down` / `range` / `unknown` | `StructureStateEnricher` | `unknown` |
| `volatility_state` | str | `low` / `medium` / `high` / `unknown` | `VolatilityEnricher` | `unknown` |

**不在本次接口范围内的 DMC Stub Enrichers（全部返回 `unknown`）：**
- `orderflow_state`、`macro_state`、`oi_state`、`cvd_state`、`funding_state`、`coinbase_premium_state`、`etf_flow_state`

### 3.3 可选扩展字段

| 字段 | 来源 | 何时输出 |
|------|------|---------|
| `setup_type` | DMC `export_trade_log_csv()` 中的 `SETUP_TYPE_LABEL` | 仅当 DMC 侧能可靠提供（current: BTP 系列返回 A/B/C，其余返回 `unknown`） |

### 3.4 预留 DMC 直接输出 SSS CSV 的能力

如果 DMC 未来能调用 `export_trade_log_csv() → df` 直接输出完整的 trade log CSV，则该 CSV 可直接作为 SSS 的输入（跳过 TradingView 转换步骤）。这种情况下 DMC 提供全部字段：

```
trade_id, strategy_name, symbol, direction, entry_time, exit_time,
entry_price, exit_price, pnl_R, pnl_usd, exit_reason,
session, regime, regime_snapshot_id, structure_state, volatility_state,
orderflow_state, macro_state, oi_state, cvd_state, funding_state,
coinbase_premium_state, etf_flow_state, setup_type
```

此时 SSS `tradingview_converter.py` 可以跳过（因为输入已是 canonical 格式）。

---

## 4. 字段定义与允许值

### 4.1 session

| 值 | UTC 范围 | DMC SessionEnricher |
|----|---------|-------------------|
| `Asia` | 00:00–07:00, 21:00–24:00 | ✅ |
| `London` | 07:00–12:00 | ✅ |
| `overlap` | 12:00–16:00 | ✅ |
| `NY` | 16:00–21:00 | ✅ |
| `weekend` | 周六全天 + 周日全天 | ✅ |

**注意：** DMC 的 `SessionEnricher` 与 SSS 的 `label_quality.classify_session()` 时段划分略有不同。DMC 版本（trade_log.py）没有分层优先级，且 21:00–24:00 直接映射为 Asia。SSS 版本（label_quality.py）有 weekend 覆盖 + overlap 优先。在实际对接中，**DMC SessionEnricher 覆盖 SSS label_quality 的 session**（因为 DMC 直接知道入场时间原始值，不依赖 SSS 已有的 session 字段）。

### 4.2 regime

| 值 | 来源 | 说明 |
|----|------|------|
| `trend_up` | DMC `RegimeEnricher` | 4H EMA200 斜率 > 0.0005 |
| `trend_down` | DMC `RegimeEnricher` | 4H EMA200 斜率 < -0.0005 |
| `range` | DMC `RegimeEnricher` | 其余 |
| `unknown` | — | 标签不可用（数据缺失或入场时间早于 parquet 第一条） |

### 4.3 regime_snapshot_id

格式：`{regime}_{snapshot}`

| 粒度 | 格式 | 示例 |
|------|------|------|
| `day` | `{regime}_{YYYYMMDD}` | `trend_up_20250601` |
| `week` | `{regime}_W{ww}_{yyyy}` | `trend_up_W22_2025` |
| `month` | `{regime}_{YYYYMM}` | `trend_up_202506` |

建议使用 `week`（默认）以保持 snapshot unique count ≤ 200。

### 4.4 structure_state

| 值 | 来源 |
|----|------|
| `trend_up` / `trend_down` / `range` | 直接复制自 `regime` |
| `unknown` | regime 不可用 |

升级路径（DMC v2）：ADX / Choppiness Index 替换简单的复制，产生 `trending / ranging / chopping / expanding`。

### 4.5 volatility_state

| 值 | 来源 |
|----|------|
| `low` | 4H ATR(14) 近 40 期百分位 < 0.33 |
| `medium` | 4H ATR(14) 近 40 期百分位 0.33–0.67 |
| `high` | 4H ATR(14) 近 40 期百分位 ≥ 0.67 |
| `unknown` | 标签不可用 |

### 4.6 setup_type（可选）

| 值 | 来源 |
|----|------|
| `A` / `B` / `C` | DMC `SETUP_TYPE_LABEL`（仅 BTP 系列有意义） |
| `unknown` | 非 BTP 策略或不提供 |

---

## 5. 时间对齐规则（防 Lookahead Bias）

### 核心规则

**对于任何需要 4H parquet 数据的标签（regime, volatility）：**

```
entry_time = trade 入场时间（UTC, tz-naive）
可用数据    = parquet rows where index <= entry_time
最近封闭 bar = 可用数据.iloc[-1]
```

**当前 DMC `RegimeEnricher` 和 `VolatilityEnricher` 已实现这个规则：**
- `ema_before = ema[ema.index <= entry_ts_cmp]` → 取 入场时间之前已封闭的 bar
- `atr_before = atr[atr.index <= entry_ts]` → 同上

### 禁止事项

- ❌ 不使用 `entry_time` 之后的 4H 数据
- ❌ 不根据 trade 结果（pnl_R）调整标签
- ❌ 不使用任何 lookahead information

### 时区处理

- SSS DMC bridge 传入 tz-naive UTC `entry_time`
- DMC 所有 enrichers 内部统一转为 tz-naive UTC 再与 parquet index（tz-naive UTC）比较
- parquet 数据（`binance_ETHUSDT_4h.parquet`）index 也是 tz-naive UTC

---

## 6. Overwrite / Preserve Original 规则

### 默认行为（`dmc_overwrite=false`）

| 条件 | 行为 |
|------|------|
| 字段值为 `unknown`、空、null | → DMC 回填 |
| 字段已有有效值（如 session=Asia, regime=trend_up） | → 跳过，保留原值 |

### Overwrite 行为（`dmc_overwrite=true`）

| 条件 | 行为 |
|------|------|
| DMC 可为此 trade 生成标签 | → 覆盖原值 |
| DMC 不能为此 trade 生成标签 | → 保留原值（不强制写 `unknown`） |

### Audit 字段

当 `dmc_bridge.py` 启用时（`preserve_original_columns=true`），以下 audit 列被写入 CSV：

| Audit 列 | 说明 |
|----------|------|
| `original_session` | DMC 回填前的原始 session |
| `original_regime` | DMC 回填前的原始 regime |
| `original_regime_snapshot_id` | DMC 回填前的原始 snapshot_id |
| `original_structure_state` | DMC 回填前的原始 structure_state |
| `original_volatility_state` | DMC 回填前的原始 volatility_state |
| `dmc_label_source` | 固定值 `"dmc_bridge_v1"` |
| `dmc_label_version` | DMC 版本标识（从 DMC enricher 元数据获取或 fixed `"1.0"`） |
| `dmc_label_confidence` | 每个字段的置信度标记（见 §6.1） |

### 6.1 dmc_label_confidence 定义

每个标签字段附带一个置信度标记：

| 标记 | 含义 |
|------|------|
| `direct` | 标签直接由 DMC enricher 计算产生（如 session / regime / volatility） |
| `derived` | 标签由其他标签派生（如 structure_state ← regime） |
| `none` | DMC 未能为此 trade 提供标签（字段值 = `unknown`） |

格式：JSON string，例如：
```json
{"session":"direct","regime":"direct","regime_snapshot_id":"direct","structure_state":"derived","volatility_state":"direct","setup_type":"direct"}
```

---

## 7. 缺失数据处理规则

### 4H parquet 数据不存在

| 场景 | 行为 |
|------|------|
| 指定 symbol 的 `.parquet` 文件不存在 | 该 symbol 的所有 DMC 相关标签保持 `unknown`；不崩溃 |
| parquet 文件存在但无法读取（损坏 / 格式错误） | 同上 |
| 交易 symbol 不在 DMC 支持的列表中（如 SOLUSDT） | 同上 |

### 入场时间早于 parquet 数据开始时间

| 场景 | 行为 |
|------|------|
| entry_time < parquet[0].index | `regime` = `unknown`，`volatility_state` = `unknown`；`session` 不受影响（session 只需 entry_time） |

### 入场时间对应的 parquet bar 数据有 NaN

| 场景 | 行为 |
|------|------|
| EMA / ATR 计算结果为 NaN | 该字段 = `unknown` |

---

## 8. 审计报告

每次 DMC bridge 运行后生成 `*_dmc_bridge_report.md`：

```markdown
# DMC Bridge Audit Report
- generated_at_utc
- input_path / output_path
- dmc_root / snapshot_granularity / overwrite

## Field Stats
| Field | Filled | Skipped Valid | Missing |
|-------|--------|---------------|---------|
| session | 12 | 0 | 0 |
| regime | 10 | 0 | 2 |
| ...

## Scope
- Uses DMC local backtest enrichers for session/regime/structure/volatility labels.
- Does not backfill OI, funding, CVD, ETF, macro, or Coinbase premium fields.
```

---

## 9. SSS 侧改动清单

### 已有的（不需要改动）

- ✅ `dmc_bridge.py` — 已实现 5 个字段的 DMC connector
- ✅ `tradingview_converter.py` — 已集成 `--apply-dmc-labels`
- ✅ `test_dmc_bridge.py` — 5 tests passed
- ✅ `config.yaml` — 默认配置不变（input_path 仍为 cleaned_trades.csv）

### 建议改进（可选，非阻塞）

| 改动 | 优先级 | 说明 |
|------|--------|------|
| 将 `dmc_label_confidence` 加入 audit 列 | P2 | 当前未实现，见 §6.1 |
| DMC 直接输出 canonical CSV 时跳过 `tradingview_converter.py` | P2 | 减少一步转换 |
| 加 CLI 参数 `--dmc-version` 用于 audit | P3 | 方便追踪 DMC 版本变化 |

---

## 10. DMC 侧改动清单

### 已有的（不需要改动）

- ✅ `TradeEnricher` 接口 + `SessionEnricher` / `RegimeEnricher` / `StructureStateEnricher` / `VolatilityEnricher`
- ✅ `export_trade_log_csv()` 导出函数 + `STRATEGY_META` 映射
- ✅ 4H parquet 数据路径约定（`data/binance_{symbol}_4h.parquet`）

### 建议改进（可选，非阻塞）

| 改动 | 优先级 | 说明 |
|------|--------|------|
| `StructureStateEnricher` 升级为 ADX-based | P2 | 当前直接复制 regime，v2 可用 ADX 区分 range/chop/expansion |
| `VolatilityEnricher` 增加 ATR14 原始值输出（可选） | P3 | 便于 SSS 做更细的波动率分析 |
| `setup_type` 非 BTP 策略也输出有意义的 label（如 "default" / "single"） | P3 | 当前仅 BTP 系列返回 A/B/C，其余为 "unknown" |

---

## 11. 完整数据流

```
┌──────────────────────┐
│  DMC-Sisie-Quantive  │
│                       │
│  run_combined_backtest│ → PortfolioManager.trades → export_trade_log_csv()
│       ↓               │                    ↓
│  TradeEnricher        │      → DMC CSV 输出（可选，直接当 SSS 输入）
│   - SessionEnricher   │
│   - RegimeEnricher    │
│   - StructureEnricher │
│   - VolatilityEnricher│
│   - Stub Enrichers    │
└───────────────────────┘
           │
           │ 方式 A: DMC CSV → tradingview_converter 跳过 → SSS canonical CSV
           │ 方式 B: TradingView CSV → tradingview_converter + --apply-dmc-labels
           │                  ↓
           │         dmc_bridge.py 调用 DMC enrichers
           │                  ↓
           └──────→ SSS canonical CSV with DMC labels
                              ↓
                     label_quality.py（可选：修复剩余的 session/structure/snapshot）
                              ↓
                     label_enrichment.py（CoinGlass OI/Funding/ETF/Macro 回填）
                              ↓
                     main.py（评分 pipeline）
```

---

## 12. 验收标准

### SSS 侧

- [ ] `PYTHONPATH=src python3 -m pytest tests/test_dmc_bridge.py` 全部通过（5 passed）
- [ ] `PYTHONPATH=src python3 -m pytest tests/` 全部通过（230 passed）
- [ ] `config.yaml` input_path 仍为 `outputs/data_quality/cleaned_trades.csv`
- [ ] Baseline 状态分布仍为 0/3/3/6
- [ ] DMC bridge 生成的 CSV 中 5 个 label 字段的 filled_count > 0（至少部分 trade 有回填）

### DMC 侧

- [ ] `SessionEnricher`, `RegimeEnricher`, `StructureStateEnricher`, `VolatilityEnricher` 全部可用
- [ ] `export_trade_log_csv()` 输出的 CSV 包含所有 24 个标准列
- [ ] 生成的 CSV 可以通过 SSS 的 `data_loader.load_trades()` 校验

### 接口对接

- [ ] SSS 可以从 DMC bridge 获取 session / regime / regime_snapshot_id / structure_state / volatility_state
- [ ] 标签不包含 lookahead bias（使用 <= entry_time 的数据）
- [ ] DMC bridge audit report 生成正确
- [ ] 不改变 Enable Score / status / performance matrix

---

## 13. 测试计划

### SSS 侧测试（已覆盖）

| 测试 | 文件 |
|------|------|
| dmc_bridge 能回填 5 个字段 | `test_dmc_bridge.py::test_dmc_bridge_backfills_supported_fields` |
| 默认不覆盖有效标签 | `test_dmc_bridge.py::test_dmc_bridge_does_not_overwrite_valid_labels_by_default` |
| overwrite 模式可覆盖 | `test_dmc_bridge.py::test_dmc_bridge_overwrite_replaces_valid_labels` |

### 建议新增测试

| 测试 | 说明 |
|------|------|
| DMC bridge 在 4H parquet 缺失时不崩溃 | trade 的 regime/volatility = unknown |
| DMC bridge 在 entry_time 早于 parquet 时不崩溃 | 同上 |
| DMC bridge audit report 包含所有 field stats | 格式检查 |
| DMC bridge 不修改 pnl_R / trade_id 等核心字段 | regression check |

---

*Generated by Strategy Enable Score System v1.1.0 — DMC Label Provider Integration Spec*
