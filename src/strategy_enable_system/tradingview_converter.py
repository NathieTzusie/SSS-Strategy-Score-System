"""
TradingView CSV converter.

Converts common TradingView strategy export formats into the canonical
Strategy Enable Score trade schema.
"""

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import pandas as pd

from .config import LabelEnrichmentConfig, LabelQualityConfig
from .dmc_bridge import DMCBridgeOptions, backfill_with_dmc, parse_symbol_4h_paths
from .label_enrichment import build_audit_report, enrich_trades
from .label_quality import fix_labels
from .schemas import ALL_EXPECTED_FIELDS


UNKNOWN = "unknown"


@dataclass
class TradingViewConvertOptions:
    """Configuration for converting TradingView CSV exports."""

    input_path: str
    output_path: str
    strategy_name: str
    symbol: str
    regime: str = UNKNOWN
    risk_usd: Optional[float] = None
    pnl_r_column: Optional[str] = None
    format: str = "auto"
    session: str = UNKNOWN
    setup_type: str = UNKNOWN
    volatility_state: str = UNKNOWN
    timezone: str = "UTC"
    apply_label_quality: bool = False
    cleaned_output_path: Optional[str] = None
    apply_enrichment: bool = False
    enriched_output_path: Optional[str] = None
    enrichment_processed_dir: str = "data/external/coinglass/processed"
    enrichment_audit_report_path: Optional[str] = None
    update_config_input: bool = False
    config_path: str = "config.yaml"
    apply_dmc_labels: bool = False
    dmc_output_path: Optional[str] = None
    dmc_root: str = r"C:\Users\12645\DMC-Sisie-Quantive"
    dmc_snapshot_granularity: str = "day"
    dmc_overwrite: bool = False
    dmc_audit_report_path: Optional[str] = None
    dmc_symbol_4h_paths: Optional[dict[str, str]] = None


def convert_tradingview_csv(options: TradingViewConvertOptions) -> pd.DataFrame:
    """Convert a TradingView CSV export and write canonical trade CSV output."""
    if options.format not in {"auto", "closed", "paired"}:
        raise ValueError("format must be one of: auto, closed, paired")
    if not os.path.exists(options.input_path):
        raise FileNotFoundError(f"TradingView CSV not found: {options.input_path}")

    raw = pd.read_csv(options.input_path)
    if raw.empty:
        raise ValueError("TradingView CSV is empty.")

    normalized = _normalize_columns(raw)
    inferred = options.format
    if inferred == "auto":
        inferred = _infer_format(normalized)

    if inferred == "closed":
        trades = _convert_closed_trades(normalized, options)
    elif inferred == "paired":
        trades = _convert_paired_events(normalized, options)
    else:
        raise ValueError(f"Unsupported TradingView format: {inferred}")

    canonical = _build_canonical_frame(trades, options)
    os.makedirs(os.path.dirname(options.output_path) or ".", exist_ok=True)
    canonical.to_csv(options.output_path, index=False)
    working_df = canonical
    working_path = options.output_path
    dmc_result = None
    if options.apply_dmc_labels:
        dmc_result = _write_dmc_bridge_csv(working_df, working_path, options)
        working_df = dmc_result["dataframe"]
        working_path = dmc_result["output_path"]

    cleaned_path = None
    label_fixes: Optional[Dict[str, int]] = None
    cleaned_df: Optional[pd.DataFrame] = None
    if options.apply_label_quality or options.apply_enrichment:
        cleaned_path, label_fixes, cleaned_df = _write_label_quality_cleaned_csv(working_df, options)
        working_df = cleaned_df
        working_path = cleaned_path
    enrichment_result = None
    if options.apply_enrichment:
        if cleaned_df is None or cleaned_path is None:
            raise RuntimeError("Label quality output is required before enrichment.")
        enrichment_result = _write_label_enrichment_csv(cleaned_df, cleaned_path, options)
    config_updated = False
    if options.update_config_input:
        final_input_path = _final_config_input_path(options)
        config_updated = update_config_input_path(options.config_path, final_input_path)
    _write_conversion_report(raw, canonical, options, inferred)
    if options.apply_dmc_labels:
        _write_dmc_bridge_report_note(options, dmc_result)
    if options.apply_label_quality or options.apply_enrichment:
        _write_label_quality_report_note(options, cleaned_path, label_fixes)
    if options.apply_enrichment:
        _write_label_enrichment_report_note(options, enrichment_result)
    if options.update_config_input:
        _write_config_update_report_note(options, config_updated)
    return canonical


def _write_label_quality_cleaned_csv(
    source: pd.DataFrame,
    options: TradingViewConvertOptions,
) -> tuple[str, Dict[str, int], pd.DataFrame]:
    """Apply label quality fixes to converted trades and write a cleaned CSV."""
    cleaned = source.copy()
    fixes = fix_labels(cleaned, LabelQualityConfig(enabled=True))
    output_path = options.cleaned_output_path or _default_cleaned_output_path(options.output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cleaned.to_csv(output_path, index=False)
    return output_path, fixes, cleaned


def _default_cleaned_output_path(output_path: str) -> str:
    """Build default cleaned CSV path next to the converted output."""
    base, ext = os.path.splitext(output_path)
    return f"{base}_cleaned{ext or '.csv'}"


def _write_dmc_bridge_csv(
    source: pd.DataFrame,
    source_path: str,
    options: TradingViewConvertOptions,
) -> Dict[str, Any]:
    """Apply DMC bridge labels to converted trades and write a DMC-labeled CSV."""
    output_path = options.dmc_output_path or _default_dmc_output_path(options.output_path)
    temp_input_path = source_path
    if source_path != options.output_path:
        temp_input_path = source_path
    bridge_options = DMCBridgeOptions(
        input_path=temp_input_path,
        output_path=output_path,
        dmc_root=options.dmc_root,
        snapshot_granularity=options.dmc_snapshot_granularity,
        overwrite=options.dmc_overwrite,
        audit_report_path=options.dmc_audit_report_path,
        symbol_4h_paths=options.dmc_symbol_4h_paths,
    )
    result = backfill_with_dmc(bridge_options)
    return {
        "output_path": output_path,
        "audit_report_path": options.dmc_audit_report_path or _default_dmc_audit_report_path(output_path),
        "dataframe": result,
    }


def _default_dmc_output_path(output_path: str) -> str:
    """Build default DMC-labeled CSV path next to the converted output."""
    base, ext = os.path.splitext(output_path)
    return f"{base}_dmc_labeled{ext or '.csv'}"


def _default_dmc_audit_report_path(output_path: str) -> str:
    """Build default DMC bridge report path for a DMC-labeled CSV."""
    base, _ = os.path.splitext(output_path)
    return f"{base}_dmc_bridge_report.md"


def _write_label_enrichment_csv(
    cleaned: pd.DataFrame,
    cleaned_path: str,
    options: TradingViewConvertOptions,
) -> Dict[str, Any]:
    """Apply label enrichment to cleaned trades and write enriched CSV plus audit."""
    enriched = cleaned.copy()
    config = LabelEnrichmentConfig(
        enabled=True,
        input_path=cleaned_path,
        output_path=options.enriched_output_path or _default_enriched_output_path(options.output_path),
        audit_report_path=(
            options.enrichment_audit_report_path
            or _default_enrichment_audit_report_path(options.output_path)
        ),
        processed_dir=options.enrichment_processed_dir,
    )
    stats, unknown_symbols = enrich_trades(enriched, config.processed_dir, config)
    os.makedirs(os.path.dirname(config.output_path) or ".", exist_ok=True)
    enriched.to_csv(config.output_path, index=False)

    report = build_audit_report(
        cleaned_path,
        config.processed_dir,
        config.output_path,
        stats,
        unknown_symbols,
        config,
    )
    os.makedirs(os.path.dirname(config.audit_report_path) or ".", exist_ok=True)
    with open(config.audit_report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return {
        "enriched_output_path": config.output_path,
        "enrichment_audit_report_path": config.audit_report_path,
        "stats": stats,
        "unknown_symbols": unknown_symbols,
    }


def _default_enriched_output_path(output_path: str) -> str:
    """Build default enriched CSV path next to the converted output."""
    base, ext = os.path.splitext(output_path)
    return f"{base}_enriched{ext or '.csv'}"


def _default_enrichment_audit_report_path(output_path: str) -> str:
    """Build default enrichment audit report path next to the converted output."""
    base, _ = os.path.splitext(output_path)
    return f"{base}_enrichment_audit_report.md"


def _final_config_input_path(options: TradingViewConvertOptions) -> str:
    """Return the final CSV path that should be appended to config input_path."""
    if options.apply_enrichment:
        return options.enriched_output_path or _default_enriched_output_path(options.output_path)
    if options.apply_dmc_labels:
        return options.dmc_output_path or _default_dmc_output_path(options.output_path)
    return options.output_path


def update_config_input_path(config_path: str, input_path: str) -> bool:
    """Append a converted/enriched CSV path to config.yaml input_path.

    Returns True when the file was changed, False when the path already existed.
    The implementation edits only the top-level input_path block to preserve the
    rest of config.yaml comments and formatting.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    normalized_input = _normalize_config_path(input_path)
    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    start_idx = None
    for idx, line in enumerate(lines):
        if re.match(r"^input_path\s*:", line):
            start_idx = idx
            break
    if start_idx is None:
        raise ValueError("config.yaml does not contain a top-level input_path block.")

    block_end = start_idx + 1
    while block_end < len(lines):
        line = lines[block_end]
        if line.strip() == "" or line.lstrip().startswith("#") or line.startswith((" ", "\t")):
            block_end += 1
            continue
        break

    existing_paths = []
    item_indent = "  "
    for line in lines[start_idx + 1:block_end]:
        match = re.match(r"^(\s*)-\s*[\"']?([^\"'\n#]+)", line)
        if match:
            item_indent = match.group(1)
            existing_paths.append(_normalize_config_path(match.group(2).strip()))

    inline_match = re.match(r"^input_path\s*:\s*(.+?)\s*$", lines[start_idx])
    if inline_match and inline_match.group(1).strip() not in {"", "[]"} and not existing_paths:
        existing = inline_match.group(1).strip().strip("\"'")
        existing_paths.append(_normalize_config_path(existing))
        lines[start_idx] = "input_path:\n"
        lines.insert(start_idx + 1, f'{item_indent}- "{existing}"\n')
        block_end += 1

    if normalized_input in existing_paths:
        return False

    insert_line = f'{item_indent}- "{normalized_input}"\n'
    lines.insert(block_end, insert_line)
    with open(config_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True


def _normalize_config_path(path: str) -> str:
    """Normalize paths for config.yaml while keeping them human-readable."""
    return str(path).replace("\\", "/")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with stable snake_case column names."""
    renamed = {}
    for col in df.columns:
        name = str(col).strip().lower()
        name = name.replace("#", "number")
        name = re.sub(r"[%()/\\.-]+", " ", name)
        name = re.sub(r"[^a-z0-9]+", "_", name)
        name = name.strip("_")
        renamed[col] = name
    return df.rename(columns=renamed)


def _infer_format(df: pd.DataFrame) -> str:
    """Infer whether CSV rows are closed trades or entry/exit events."""
    cols = set(df.columns)
    if _find_col(cols, ["entry_time", "entry_date_time", "entry_date"]) and _find_col(
        cols, ["exit_time", "exit_date_time", "exit_date"]
    ):
        return "closed"

    type_col = _find_col(cols, ["type", "order_type", "action"])
    trade_col = _find_col(cols, ["trade_number", "trade_no", "trade_id", "number"])
    time_col = _find_col(cols, ["date_time", "date_and_time", "time", "date"])
    if type_col and trade_col and time_col:
        values = df[type_col].astype(str).str.lower()
        if values.str.contains("entry|exit").any():
            return "paired"

    raise ValueError(
        "Cannot infer TradingView CSV format. Use --format closed or --format paired, "
        "or provide a CSV with entry/exit time columns."
    )


def _convert_closed_trades(df: pd.DataFrame, options: TradingViewConvertOptions) -> pd.DataFrame:
    """Convert one-row-per-closed-trade TradingView exports."""
    cols = set(df.columns)
    entry_col = _require_col(cols, ["entry_time", "entry_date_time", "entry_date"], "entry time")
    exit_col = _require_col(cols, ["exit_time", "exit_date_time", "exit_date"], "exit time")
    direction_col = _require_col(cols, ["direction", "side", "type"], "direction")
    pnl_usd_col = _find_col(cols, ["pnl_usd", "profit", "net_profit", "net_p_l_usdt", "p_l", "pl"])
    trade_id_col = _find_col(cols, ["trade_id", "trade_number", "trade_no", "number"])
    signal_col = _find_col(cols, ["signal", "entry_signal"])

    out = pd.DataFrame()
    out["trade_id"] = (
        df[trade_id_col].apply(lambda v: f"TV_{v}") if trade_id_col else [f"TV_{i+1}" for i in range(len(df))]
    )
    out["direction"] = df[direction_col].apply(_normalize_direction)
    out["entry_time"] = _parse_datetime_series(df[entry_col], options.timezone)
    out["exit_time"] = _parse_datetime_series(df[exit_col], options.timezone)
    out["pnl_usd"] = _parse_money_series(df[pnl_usd_col]) if pnl_usd_col else 0.0
    out["pnl_R"] = _derive_pnl_r(df, out["pnl_usd"], options)
    if signal_col:
        out["setup_type"] = df[signal_col].fillna(UNKNOWN).astype(str)
    return out


def _convert_paired_events(df: pd.DataFrame, options: TradingViewConvertOptions) -> pd.DataFrame:
    """Convert TradingView entry/exit event rows into closed trades."""
    cols = set(df.columns)
    trade_col = _require_col(cols, ["trade_number", "trade_no", "trade_id", "number"], "trade number")
    type_col = _require_col(cols, ["type", "order_type", "action"], "entry/exit type")
    time_col = _require_col(cols, ["date_time", "date_and_time", "time", "date"], "event time")
    pnl_usd_col = _find_col(cols, ["pnl_usd", "profit", "net_profit", "net_p_l_usdt", "p_l", "pl"])
    signal_col = _find_col(cols, ["signal", "entry_signal"])

    rows = []
    for trade_id, group in df.groupby(trade_col, sort=False):
        types = group[type_col].astype(str).str.lower()
        entry = group[types.str.contains("entry")]
        exit_ = group[types.str.contains("exit")]
        if entry.empty or exit_.empty:
            raise ValueError(f"Trade {trade_id} does not have both entry and exit rows.")

        entry_row = entry.iloc[0]
        exit_row = exit_.iloc[-1]
        direction = _direction_from_event_text(entry_row[type_col])
        pnl_usd = _parse_money(exit_row[pnl_usd_col]) if pnl_usd_col else 0.0
        pnl_r = _derive_single_pnl_r(exit_row, pnl_usd, options)
        rows.append({
            "trade_id": f"TV_{trade_id}",
            "direction": direction,
            "entry_time": _parse_datetime(entry_row[time_col], options.timezone),
            "exit_time": _parse_datetime(exit_row[time_col], options.timezone),
            "pnl_usd": pnl_usd,
            "pnl_R": pnl_r,
            "setup_type": str(entry_row[signal_col]) if signal_col and not pd.isna(entry_row[signal_col]) else UNKNOWN,
        })
    return pd.DataFrame(rows)


def _build_canonical_frame(trades: pd.DataFrame, options: TradingViewConvertOptions) -> pd.DataFrame:
    """Build canonical SSS trade schema from converted TradingView trades."""
    canonical = trades.copy()
    canonical["strategy_name"] = options.strategy_name
    canonical["symbol"] = options.symbol
    canonical["session"] = options.session
    canonical["regime"] = options.regime
    if "setup_type" not in canonical.columns or options.setup_type != UNKNOWN:
        canonical["setup_type"] = options.setup_type
    else:
        canonical["setup_type"] = canonical["setup_type"].fillna(UNKNOWN)
    canonical["volatility_state"] = options.volatility_state

    for field in ALL_EXPECTED_FIELDS:
        if field not in canonical.columns:
            canonical[field] = UNKNOWN

    canonical["pnl_usd"] = pd.to_numeric(canonical["pnl_usd"], errors="coerce").fillna(0.0)
    canonical["pnl_R"] = pd.to_numeric(canonical["pnl_R"], errors="coerce")
    if canonical["pnl_R"].isna().any():
        rows = canonical[canonical["pnl_R"].isna()].index.tolist()
        raise ValueError(f"Could not derive pnl_R for rows: {rows}")
    if (canonical["exit_time"] < canonical["entry_time"]).any():
        rows = canonical[canonical["exit_time"] < canonical["entry_time"]].index.tolist()
        raise ValueError(f"exit_time < entry_time after conversion at rows: {rows}")

    ordered = [
        "trade_id", "strategy_name", "symbol", "direction",
        "entry_time", "exit_time", "pnl_R", "pnl_usd",
        "session", "regime", "regime_snapshot_id", "structure_state",
        "volatility_state", "orderflow_state", "macro_state",
        "oi_state", "cvd_state", "funding_state",
        "coinbase_premium_state", "etf_flow_state", "setup_type",
    ]
    return canonical[ordered].sort_values("entry_time").reset_index(drop=True)


def _derive_pnl_r(df: pd.DataFrame, pnl_usd: pd.Series, options: TradingViewConvertOptions) -> pd.Series:
    """Derive pnl_R from explicit R column or fixed risk amount."""
    cols = set(df.columns)
    pnl_r_col = _resolve_optional_column(cols, options.pnl_r_column)
    if pnl_r_col:
        return _parse_money_series(df[pnl_r_col])
    if options.risk_usd is None or options.risk_usd <= 0:
        raise ValueError("pnl_R requires --pnl-r-column or positive --risk-usd.")
    return pnl_usd.astype(float) / float(options.risk_usd)


def _derive_single_pnl_r(row: pd.Series, pnl_usd: float, options: TradingViewConvertOptions) -> float:
    """Derive a single trade pnl_R value."""
    if options.pnl_r_column:
        col = _normalize_column_name(options.pnl_r_column)
        if col not in row.index:
            raise ValueError(f"pnl_R column not found: {options.pnl_r_column}")
        return _parse_money(row[col])
    if options.risk_usd is None or options.risk_usd <= 0:
        raise ValueError("pnl_R requires --pnl-r-column or positive --risk-usd.")
    return pnl_usd / float(options.risk_usd)


def _find_col(cols: Iterable[str], candidates: list[str]) -> Optional[str]:
    """Find the first available column from candidate names."""
    colset = set(cols)
    for candidate in candidates:
        normalized = _normalize_column_name(candidate)
        if normalized in colset:
            return normalized
    return None


def _require_col(cols: Iterable[str], candidates: list[str], label: str) -> str:
    """Find a required column or raise a clear error."""
    found = _find_col(cols, candidates)
    if not found:
        raise ValueError(f"Missing TradingView {label} column. Tried: {candidates}")
    return found


def _resolve_optional_column(cols: Iterable[str], col: Optional[str]) -> Optional[str]:
    """Resolve a user-provided optional column name after normalization."""
    if not col:
        return None
    normalized = _normalize_column_name(col)
    if normalized not in set(cols):
        raise ValueError(f"Column not found: {col}")
    return normalized


def _normalize_column_name(name: str) -> str:
    """Normalize a single column name using the converter convention."""
    return _normalize_columns(pd.DataFrame(columns=[name])).columns[0]


def _normalize_direction(value: Any) -> str:
    """Normalize direction-like values to long/short."""
    text = str(value).strip().lower()
    if "short" in text or text in {"sell", "s"}:
        return "short"
    if "long" in text or text in {"buy", "b"}:
        return "long"
    raise ValueError(f"Cannot infer direction from value: {value}")


def _direction_from_event_text(value: Any) -> str:
    """Infer long/short direction from a TradingView entry event."""
    text = str(value).strip().lower()
    if "short" in text:
        return "short"
    if "long" in text:
        return "long"
    return _normalize_direction(text)


def _parse_datetime_series(series: pd.Series, timezone: str) -> pd.Series:
    """Parse datetimes and return timezone-naive UTC timestamps."""
    return series.apply(lambda v: _parse_datetime(v, timezone))


def _parse_datetime(value: Any, timezone: str) -> pd.Timestamp:
    """Parse one datetime value and normalize to timezone-naive UTC."""
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"Cannot parse datetime: {value}")
    if ts.tzinfo is None:
        ts = ts.tz_localize(timezone)
    else:
        ts = ts.tz_convert(timezone)
    if timezone.upper() == "UTC":
        return ts.tz_localize(None)
    return ts.tz_convert("UTC").tz_localize(None)


def _parse_money_series(series: pd.Series) -> pd.Series:
    """Parse TradingView numeric/money strings into floats."""
    return series.apply(_parse_money).astype(float)


def _parse_money(value: Any) -> float:
    """Parse numbers like '$1,234.50', '(12.3)', or '1.2%' into floats."""
    if pd.isna(value):
        return 0.0
    text = str(value).strip()
    if text == "":
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    text = text.replace("−", "-")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", "."}:
        return 0.0
    parsed = float(text)
    return -abs(parsed) if negative else parsed


def _write_conversion_report(
    raw: pd.DataFrame,
    canonical: pd.DataFrame,
    options: TradingViewConvertOptions,
    detected_format: str,
) -> None:
    """Write a small audit report next to the converted CSV."""
    report_path = os.path.splitext(options.output_path)[0] + "_conversion_report.md"
    lines = [
        "# TradingView Conversion Report",
        "",
        f"- input_path: `{options.input_path}`",
        f"- output_path: `{options.output_path}`",
        f"- detected_format: `{detected_format}`",
        f"- raw_rows: {len(raw)}",
        f"- converted_trades: {len(canonical)}",
        f"- strategy_name: `{options.strategy_name}`",
        f"- symbol: `{options.symbol}`",
        f"- regime: `{options.regime}`",
        f"- risk_usd: `{options.risk_usd}`",
        "",
        "This converter does not infer market regime or orderflow labels.",
        "Missing state fields are filled with `unknown` for downstream label tools.",
    ]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_label_quality_report_note(
    options: TradingViewConvertOptions,
    cleaned_path: Optional[str],
    fixes: Optional[Dict[str, int]],
) -> None:
    """Append label quality output details to the conversion audit report."""
    report_path = os.path.splitext(options.output_path)[0] + "_conversion_report.md"
    lines = [
        "",
        "## Label Quality Auto-Fix",
        "",
        f"- enabled: `{options.apply_label_quality}`",
        f"- cleaned_output_path: `{cleaned_path}`",
    ]
    if fixes:
        lines.extend([
            f"- session_fixed: {fixes.get('session_fixed', 0)}",
            f"- structure_state_fixed: {fixes.get('structure_state_fixed', 0)}",
            f"- snapshot_normalized: {fixes.get('snapshot_normalized', 0)}",
            f"- trade_id_deduplicated: {fixes.get('trade_id_deduplicated', 0)}",
        ])
    lines.extend([
        "",
        "For multiple converted TradingView files, run the standalone label quality tool on all files together before scoring.",
    ])
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines))


def _write_label_enrichment_report_note(
    options: TradingViewConvertOptions,
    result: Optional[Dict[str, Any]],
) -> None:
    """Append enrichment output details to the conversion audit report."""
    report_path = os.path.splitext(options.output_path)[0] + "_conversion_report.md"
    lines = [
        "",
        "## Label Enrichment Auto-Fill",
        "",
        f"- enabled: `{options.apply_enrichment}`",
        f"- processed_dir: `{options.enrichment_processed_dir}`",
    ]
    if result:
        lines.extend([
            f"- enriched_output_path: `{result.get('enriched_output_path')}`",
            f"- enrichment_audit_report_path: `{result.get('enrichment_audit_report_path')}`",
            f"- unknown_symbols: {result.get('unknown_symbols', 0)}",
        ])
        stats = result.get("stats", {})
        for field in ["oi_state", "funding_state", "orderflow_state", "etf_flow_state", "macro_state"]:
            field_stats = stats.get(field, {})
            lines.append(f"- {field}_filled: {field_stats.get('filled', 0)}")
    lines.extend([
        "",
        "Enrichment uses already processed external market data only; it does not fetch live API data.",
    ])
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines))


def _write_dmc_bridge_report_note(
    options: TradingViewConvertOptions,
    result: Optional[Dict[str, Any]],
) -> None:
    """Append DMC bridge output details to the conversion audit report."""
    report_path = os.path.splitext(options.output_path)[0] + "_conversion_report.md"
    lines = [
        "",
        "## DMC Bridge Labels",
        "",
        f"- enabled: `{options.apply_dmc_labels}`",
        f"- dmc_root: `{options.dmc_root}`",
        f"- snapshot_granularity: `{options.dmc_snapshot_granularity}`",
        f"- overwrite: `{options.dmc_overwrite}`",
    ]
    if result:
        lines.extend([
            f"- dmc_output_path: `{result.get('output_path')}`",
            f"- dmc_audit_report_path: `{result.get('audit_report_path')}`",
        ])
    lines.extend([
        "",
        "DMC bridge backfills local backtest labels only: session, regime, regime_snapshot_id, structure_state, volatility_state.",
    ])
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines))


def _write_config_update_report_note(options: TradingViewConvertOptions, updated: bool) -> None:
    """Append config input_path update details to the conversion audit report."""
    report_path = os.path.splitext(options.output_path)[0] + "_conversion_report.md"
    final_input_path = (
        options.enriched_output_path or _default_enriched_output_path(options.output_path)
        if options.apply_enrichment else options.output_path
    )
    lines = [
        "",
        "## Config Input Update",
        "",
        f"- enabled: `{options.update_config_input}`",
        f"- config_path: `{options.config_path}`",
        f"- input_path_added: `{_normalize_config_path(final_input_path)}`",
        f"- changed: `{updated}`",
    ]
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines))


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser for TradingView CSV conversion."""
    parser = argparse.ArgumentParser(description="Convert TradingView CSV trades to SSS canonical CSV.")
    parser.add_argument("--input", required=True, dest="input_path", help="TradingView CSV path.")
    parser.add_argument("--output", required=True, dest="output_path", help="Output canonical CSV path.")
    parser.add_argument("--strategy-name", required=True, help="Strategy name to assign.")
    parser.add_argument("--symbol", required=True, help="Symbol to assign, e.g. BTCUSDT.")
    parser.add_argument("--regime", default=UNKNOWN, help="Regime label to assign. Default: unknown.")
    parser.add_argument("--risk-usd", type=float, default=None, help="Fixed 1R USD risk used to derive pnl_R.")
    parser.add_argument("--pnl-r-column", default=None, help="Existing TradingView column containing R multiple.")
    parser.add_argument("--format", choices=["auto", "closed", "paired"], default="auto")
    parser.add_argument("--session", default=UNKNOWN)
    parser.add_argument("--setup-type", default=UNKNOWN)
    parser.add_argument("--volatility-state", default=UNKNOWN)
    parser.add_argument("--timezone", default="UTC", help="Timezone for naive TradingView timestamps.")
    parser.add_argument(
        "--apply-label-quality",
        action="store_true",
        help="Also write a cleaned CSV after applying label quality fixes.",
    )
    parser.add_argument(
        "--cleaned-output",
        dest="cleaned_output_path",
        default=None,
        help="Optional cleaned CSV path used with --apply-label-quality.",
    )
    parser.add_argument(
        "--apply-enrichment",
        action="store_true",
        help="Also write an enriched CSV after label quality fixes.",
    )
    parser.add_argument(
        "--enriched-output",
        dest="enriched_output_path",
        default=None,
        help="Optional enriched CSV path used with --apply-enrichment.",
    )
    parser.add_argument(
        "--enrichment-processed-dir",
        default="data/external/coinglass/processed",
        help="Processed external market data directory used with --apply-enrichment.",
    )
    parser.add_argument(
        "--enrichment-audit-report",
        dest="enrichment_audit_report_path",
        default=None,
        help="Optional enrichment audit report path used with --apply-enrichment.",
    )
    parser.add_argument(
        "--update-config-input",
        action="store_true",
        help="Append this run's final CSV to config.yaml input_path.",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        default="config.yaml",
        help="Config path used with --update-config-input. Default: config.yaml.",
    )
    parser.add_argument(
        "--apply-dmc-labels",
        action="store_true",
        help="Backfill local DMC engine labels after conversion.",
    )
    parser.add_argument(
        "--dmc-output",
        dest="dmc_output_path",
        default=None,
        help="Optional DMC-labeled CSV path used with --apply-dmc-labels.",
    )
    parser.add_argument("--dmc-root", default=r"C:\Users\12645\DMC-Sisie-Quantive")
    parser.add_argument("--dmc-snapshot-granularity", choices=["day", "week", "month"], default="day")
    parser.add_argument("--dmc-overwrite", action="store_true", help="Overwrite existing DMC-supported labels.")
    parser.add_argument("--dmc-audit-report", dest="dmc_audit_report_path", default=None)
    parser.add_argument(
        "--dmc-symbol-4h-path",
        action="append",
        default=None,
        help="Override DMC 4H path, e.g. BTCUSDT=C:/path/binance_BTCUSDT_4h.parquet.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    raw_args = vars(args)
    raw_args["dmc_symbol_4h_paths"] = parse_symbol_4h_paths(raw_args.pop("dmc_symbol_4h_path"))
    options = TradingViewConvertOptions(**raw_args)
    config_input_path = _final_config_input_path(options)
    converted = convert_tradingview_csv(options)
    print(json.dumps({
        "status": "ok",
        "output_path": options.output_path,
        "cleaned_output_path": (
            options.cleaned_output_path or _default_cleaned_output_path(options.output_path)
            if options.apply_label_quality or options.apply_enrichment else None
        ),
        "enriched_output_path": (
            options.enriched_output_path or _default_enriched_output_path(options.output_path)
            if options.apply_enrichment else None
        ),
        "dmc_output_path": (
            options.dmc_output_path or _default_dmc_output_path(options.output_path)
            if options.apply_dmc_labels else None
        ),
        "config_path": options.config_path if options.update_config_input else None,
        "config_input_path": _normalize_config_path(config_input_path) if options.update_config_input else None,
        "converted_trades": len(converted),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
