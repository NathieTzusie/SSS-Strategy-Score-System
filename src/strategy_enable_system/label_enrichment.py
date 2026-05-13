"""
Label Enrichment Engine for Strategy Enable Score System v1.1 (P2-8).

Backfills oi_state / funding_state / orderflow_state / etf_flow_state / macro_state
from CoinGlass processed CSV data, with lookahead bias prevention.

Run standalone:
  PYTHONPATH=src python -m strategy_enable_system.label_enrichment --config config.yaml
  PYTHONPATH=src python -m strategy_enable_system.label_enrichment --config config.yaml --dry-run
"""

import os
import sys
import argparse
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from .config import load_config, LabelEnrichmentConfig

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Symbol mapping
# ---------------------------------------------------------------------------

SYMBOL_MAP = {"BTCUSDT": "BTC", "ETHUSDT": "ETH", "BTC": "BTC", "ETH": "ETH"}


def map_to_coinglass_symbol(trade_symbol: str) -> Optional[str]:
    return SYMBOL_MAP.get(str(trade_symbol).upper(), None)


def is_missing(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    s = str(val).strip().lower()
    return s in ("", "unknown", "nan")


# ---------------------------------------------------------------------------
# Lookahead-safe time alignment
# ---------------------------------------------------------------------------

def find_most_recent(df: pd.DataFrame, entry_time: pd.Timestamp, date_only: bool = False) -> Optional[pd.Series]:
    """Find the most recent row with datetime_utc <= entry_time."""
    if df is None or len(df) == 0:
        return None
    times = pd.to_datetime(df["datetime_utc"])
    if date_only:
        entry_date = entry_time.normalize()
        mask = times.dt.normalize() <= entry_date
    else:
        mask = times <= entry_time
    candidates = df[mask]
    if len(candidates) == 0:
        return None
    return candidates.iloc[-1]


def find_event_window(calendar_df: pd.DataFrame, entry_time: pd.Timestamp, window_hours: int) -> bool:
    """Check if entry_time falls within an event window."""
    if calendar_df is None or len(calendar_df) == 0:
        return False
    window = pd.Timedelta(hours=window_hours)
    times = pd.to_datetime(calendar_df["publish_timestamp"], unit="s", errors="coerce")
    mask = (times.notna()) & (abs(times - entry_time) <= window)
    return mask.any()


# ---------------------------------------------------------------------------
# Label enrichment rules
# ---------------------------------------------------------------------------

def enrich_oi_state(df: pd.DataFrame, entry_time: pd.Timestamp, thresholds) -> Optional[str]:
    row = find_most_recent(df, entry_time, date_only=True)
    if row is None:
        return None
    # Need at least 2 rows to compute pct_change
    times = pd.to_datetime(df["datetime_utc"])
    mask = times.dt.normalize() <= entry_time.normalize()
    candidates = df[mask]
    if len(candidates) < 2:
        return None
    vals = candidates["close"].values
    pct = (vals[-1] - vals[-2]) / abs(vals[-2]) if vals[-2] != 0 else 0.0
    if pct >= thresholds.oi_change_pct_rising:
        return "rising"
    elif pct <= thresholds.oi_change_pct_falling:
        return "falling"
    return "flat"


def enrich_funding_state(df: pd.DataFrame, entry_time: pd.Timestamp, thresholds) -> Optional[str]:
    row = find_most_recent(df, entry_time, date_only=True)
    if row is None:
        return None
    val = row["close"]
    if val >= thresholds.funding_positive:
        return "positive"
    elif val <= thresholds.funding_negative:
        return "negative"
    return "neutral"


def enrich_orderflow_state(df: pd.DataFrame, entry_time: pd.Timestamp, thresholds) -> Optional[str]:
    row = find_most_recent(df, entry_time, date_only=False)
    if row is None:
        return None
    imb = row["taker_imbalance"]
    if imb >= thresholds.taker_imbalance_bullish:
        return "bullish"
    elif imb <= thresholds.taker_imbalance_bearish:
        return "bearish"
    return "neutral"


def enrich_etf_flow_state(df: pd.DataFrame, entry_time: pd.Timestamp, thresholds) -> Optional[str]:
    row = find_most_recent(df, entry_time, date_only=True)
    if row is None:
        return None
    flow = row["flow_usd"]
    if flow >= thresholds.etf_flow_inflow_usd:
        return "inflow"
    elif flow <= thresholds.etf_flow_outflow_usd:
        return "outflow"
    return "neutral"


def enrich_macro_state(calendar_df: pd.DataFrame, etf_label: Optional[str],
                       entry_time: pd.Timestamp, thresholds) -> Optional[str]:
    if calendar_df is not None and len(calendar_df) > 0:
        times = pd.to_datetime(calendar_df["publish_timestamp"], unit="s", errors="coerce")
        window = pd.Timedelta(hours=thresholds.macro_event_window_hours)
        high_imp = calendar_df["importance_level"] >= thresholds.macro_high_importance_level
        in_event = (times.notna()) & high_imp & (abs(times - entry_time) <= window)
        if in_event.any():
            return "event_risk"
    if etf_label in ("inflow", "outflow"):
        return "flow_driven"
    return "neutral"


# ---------------------------------------------------------------------------
# Processed CSV loading
# ---------------------------------------------------------------------------

def _find_file(proc_dir: str, *patterns: str) -> Optional[str]:
    for p in patterns:
        path = os.path.join(proc_dir, p)
        if os.path.exists(path):
            return path
    return None


def load_processed_data(proc_dir: str, cg_symbol: str, config: LabelEnrichmentConfig):
    """Load all processed CSV files relevant to a symbol."""
    results = {}
    cg_lower = cg_symbol.lower()
    cg_upper = cg_symbol.upper()

    # OI
    oi = _find_file(proc_dir,
                    f"{cg_upper}_oi_agg.csv", f"{cg_lower}_oi_agg.csv",
                    f"open_interest_aggregated_{cg_upper}_1d.csv")
    if oi:
        results["oi"] = pd.read_csv(oi)
        logger.debug("  OI: %s (%d rows)", oi, len(results["oi"]))

    # Funding
    fund = _find_file(proc_dir,
                      f"{cg_upper}_funding_oiw.csv", f"{cg_lower}_funding_oiw.csv",
                      f"funding_oi_weight_{cg_upper}_1d.csv")
    if fund:
        results["funding"] = pd.read_csv(fund)
        logger.debug("  Funding: %s (%d rows)", fund, len(results["funding"]))

    # Taker
    taker = _find_file(proc_dir,
                       f"{cg_upper}_taker_agg.csv", f"{cg_lower}_taker_agg.csv",
                       f"taker_buy_sell_aggregated_{cg_upper}_1h.csv")
    if taker:
        results["taker"] = pd.read_csv(taker)
        logger.debug("  Taker: %s (%d rows)", taker, len(results["taker"]))

    # ETF
    etf = _find_file(proc_dir,
                     f"{cg_lower}_etf_flow.csv", f"{cg_upper}_etf_flow.csv",
                     f"bitcoin_etf_flow_{cg_upper}_daily.csv" if cg_upper == "BTC" else f"ethereum_etf_flow_{cg_upper}_daily.csv")
    if etf:
        results["etf"] = pd.read_csv(etf)
        logger.debug("  ETF: %s (%d rows)", etf, len(results["etf"]))

    # Calendar (global — load once)
    cal_path = _find_file(proc_dir, "calendar_economic.csv", "financial_calendar_GLOBAL_daily.csv")
    if cal_path and "calendar" not in results:
        results["calendar"] = pd.read_csv(cal_path)
        logger.debug("  Calendar: %s (%d rows)", cal_path, len(results["calendar"]))

    return results


# ---------------------------------------------------------------------------
# Main enrichment logic
# ---------------------------------------------------------------------------

def enrich_trades(trades_df: pd.DataFrame, proc_dir: str, config: LabelEnrichmentConfig):
    """Enrich trades with external market labels."""
    thresh = config.thresholds
    fields_cfg = config.fields
    preserve = config.preserve_original_columns

    stats = {
        field: {"before_unknown": 0, "after_unknown": 0, "filled": 0,
                "unchanged_valid": 0, "missing_match": 0}
        for field in ["oi_state", "funding_state", "orderflow_state", "etf_flow_state", "macro_state"]
    }
    unknown_symbols = 0
    processed_data_cache = {}

    enrich_cols = {
        "oi_state": fields_cfg.enrich_oi_state,
        "funding_state": fields_cfg.enrich_funding_state,
        "orderflow_state": fields_cfg.enrich_orderflow_state,
        "etf_flow_state": fields_cfg.enrich_etf_flow_state,
        "macro_state": fields_cfg.enrich_macro_state,
    }

    # Preserve originals
    if preserve:
        for col in ["oi_state", "funding_state", "orderflow_state", "etf_flow_state", "macro_state"]:
            orig_col = f"original_{col}"
            if orig_col not in trades_df.columns:
                if col in trades_df.columns:
                    trades_df[orig_col] = trades_df[col]
                else:
                    trades_df[orig_col] = "unknown"

    # Ensure target columns exist
    for col in ["oi_state", "funding_state", "orderflow_state", "etf_flow_state", "macro_state"]:
        if col not in trades_df.columns:
            trades_df[col] = "unknown"

    entry_times = pd.to_datetime(trades_df["entry_time"])

    for idx in trades_df.index:
        trade_sym = str(trades_df.at[idx, "symbol"])
        cg_sym = map_to_coinglass_symbol(trade_sym)

        if cg_sym is None:
            unknown_symbols += 1
            continue

        entry_dt = entry_times[idx]

        # Load processed data (cached per symbol)
        if cg_sym not in processed_data_cache:
            processed_data_cache[cg_sym] = load_processed_data(proc_dir, cg_sym, config)

        proc_data = processed_data_cache[cg_sym]

        for field, do_enrich in enrich_cols.items():
            if not do_enrich:
                continue
            current = trades_df.at[idx, field]
            if not is_missing(current):
                stats[field]["unchanged_valid"] += 1
                continue
            stats[field]["before_unknown"] += 1

            label = None
            if field == "oi_state" and "oi" in proc_data:
                label = enrich_oi_state(proc_data["oi"], entry_dt, thresh)
            elif field == "funding_state" and "funding" in proc_data:
                label = enrich_funding_state(proc_data["funding"], entry_dt, thresh)
            elif field == "orderflow_state" and "taker" in proc_data:
                label = enrich_orderflow_state(proc_data["taker"], entry_dt, thresh)
            elif field == "etf_flow_state" and "etf" in proc_data:
                label = enrich_etf_flow_state(proc_data["etf"], entry_dt, thresh)
            elif field == "macro_state":
                cal = proc_data.get("calendar", None)
                etf_label = None
                if "etf" in proc_data:
                    etf_row = find_most_recent(proc_data["etf"], entry_dt, date_only=True)
                    if etf_row is not None:
                        flow = etf_row["flow_usd"]
                        if flow >= thresh.etf_flow_inflow_usd:
                            etf_label = "inflow"
                        elif flow <= thresh.etf_flow_outflow_usd:
                            etf_label = "outflow"
                label = enrich_macro_state(cal, etf_label, entry_dt, thresh)

            if label is not None:
                trades_df.at[idx, field] = label
                stats[field]["filled"] += 1
            else:
                stats[field]["missing_match"] += 1

    # Compute after counts
    for field in stats:
        after_unk = trades_df[field].apply(is_missing).sum() if field in trades_df.columns else stats[field]["before_unknown"]
        stats[field]["after_unknown"] = after_unk

    return stats, unknown_symbols


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------

def build_audit_report(trades_path: str, proc_dir: str, output_path: str,
                       stats: dict, unknown_symbols: int, config: LabelEnrichmentConfig) -> str:
    lines = []
    def h(lvl, text): lines.append(f"{'#' * lvl} {text}")

    h(1, "Label Enrichment Audit Report")
    lines.append(f"**生成时间：** {datetime.utcnow().isoformat()} UTC")
    lines.append(f"**输入 CSV：** {trades_path}")
    lines.append(f"**processed_dir：** {proc_dir}")
    lines.append(f"**输出 CSV：** {output_path}")
    lines.append("")

    total = sum(s.get("before_unknown", 0) + s.get("unchanged_valid", 0)
                for s in stats.values()) // max(len(stats), 1) if stats else 0
    lines.append(f"**总交易数：** {total}")
    lines.append(f"**Unknown symbol 数：** {unknown_symbols}")
    lines.append("")

    h(2, "各字段回填统计")
    lines.append("| Field | Before Unknown | Filled | Unchanged Valid | Missing Match | After Unknown |")
    lines.append("|-------|---------------|--------|-----------------|---------------|---------------|")
    for f in ["oi_state", "funding_state", "orderflow_state", "etf_flow_state", "macro_state"]:
        s = stats.get(f, {})
        lines.append(f"| {f} | {s.get('before_unknown', 0)} | {s.get('filled', 0)} | "
                     f"{s.get('unchanged_valid', 0)} | {s.get('missing_match', 0)} | {s.get('after_unknown', 0)} |")
    lines.append("")

    h(2, "外部 Processed 文件")
    for root, dirs, files in os.walk(proc_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            try:
                df = pd.read_csv(fpath)
                lines.append(f"- `{fpath}`: {len(df)} rows")
                if "datetime_utc" in df.columns:
                    dts = pd.to_datetime(df["datetime_utc"])
                    lines.append(f"  - datetime_utc range: {dts.min()} → {dts.max()}")
            except Exception:
                lines.append(f"- `{fpath}`: (unable to read)")

    lines.append("")

    h(2, "Lookahead Bias 防护")
    lines.append(f"- prevent_lookahead: **{config.alignment.prevent_lookahead}**")
    lines.append("- 所有标签使用 entry_time 之前已完成区间的数据")
    lines.append("- Futures 数据：使用 datetime_utc <= entry_time 的最近记录")
    lines.append("- ETF / OI / Funding 日级数据：使用日期 <= entry_time 所在日期的记录")
    lines.append("")

    h(2, "重要声明")
    lines.append("- ⚠️ 本次 **未修改** cleaned_trades.csv")
    lines.append("- ⚠️ 本次 **未修改** 评分 pipeline（main.py）")
    lines.append("- ⚠️ 本次 **未修改** Enable Score、Monte Carlo、Performance Matrix")
    lines.append("- ⚠️ `enriched_trades.csv` 不作为默认评分输入")
    lines.append("- ⚠️ 所有被回填字段的原始值保留于 `original_*` 列")
    if unknown_symbols > 0:
        lines.append(f"- ⚠️ {unknown_symbols} 笔交易的 symbol 无法映射到 CoinGlass 数据")
    lines.append("")

    lines.append("*Generated by Strategy Enable Score System v1.1 — P2-8 Label Enrichment*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run(config_path: str, input_override: str = None, output_override: str = None,
        proc_dir_override: str = None, dry_run: bool = False):
    full_config = load_config(config_path)
    le = full_config.label_enrichment

    if not le.enabled and not dry_run:
        logger.warning("label_enrichment.enabled is False. Use --dry-run to preview or enable in config.")
        return

    trades_path = input_override or le.input_path
    output_path = output_override or le.output_path
    proc_dir = proc_dir_override or le.processed_dir

    logger.info("Input: %s", trades_path)
    logger.info("Processed dir: %s", proc_dir)
    logger.info("Output: %s", output_path)

    if not os.path.exists(trades_path):
        raise FileNotFoundError(f"Trades CSV not found: {trades_path}")
    if not os.path.exists(proc_dir):
        logger.warning("Processed dir not found: %s — enrichment will have no external data", proc_dir)

    trades_df = pd.read_csv(trades_path)
    logger.info("Loaded %d trades", len(trades_df))

    if dry_run:
        logger.info("=== DRY RUN — no enriched CSV will be written ===")
        cg_syms = set()
        for sym in trades_df["symbol"].unique():
            cg = map_to_coinglass_symbol(sym)
            if cg:
                cg_syms.add(cg)
        logger.info("Trade symbols mapped to CoinGlass: %s", cg_syms)
        logger.info("Files expected in %s:", proc_dir)
        if os.path.exists(proc_dir):
            for f in sorted(os.listdir(proc_dir)):
                logger.info("  - %s", f)
        else:
            logger.info("  (directory does not exist)")
        return

    stats, unknown_syms = enrich_trades(trades_df, proc_dir, le)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    trades_df.to_csv(output_path, index=False)
    logger.info("Enriched CSV: %s", output_path)

    report = build_audit_report(trades_path, proc_dir, output_path, stats, unknown_syms, le)
    report_path = le.audit_report_path
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Audit report: %s", report_path)

    # Summary
    for f in ["oi_state", "funding_state", "orderflow_state", "etf_flow_state", "macro_state"]:
        s = stats.get(f, {})
        logger.info("  %s: before_unknown=%d filled=%d unchanged=%d missing=%d after_unknown=%d",
                    f, s.get("before_unknown", 0), s.get("filled", 0),
                    s.get("unchanged_valid", 0), s.get("missing_match", 0), s.get("after_unknown", 0))


def main():
    parser = argparse.ArgumentParser(description="SSS v1.1 — Label Enrichment Engine (P2-8)")
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--input", "-i", default=None, help="Override input trades CSV")
    parser.add_argument("--output", "-o", default=None, help="Override output enriched CSV")
    parser.add_argument("--processed-dir", "-p", default=None, help="Override processed data dir")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()
    run(args.config, args.input, args.output, args.processed_dir, args.dry_run)


if __name__ == "__main__":
    main()
