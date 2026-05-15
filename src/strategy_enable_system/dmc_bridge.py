"""
DMC bridge for SSS trade labels.

This module lets SSS call the local DMC-Sisie-Quantive backtest engine
enrichers to backfill labels on TradingView-converted CSV files.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import importlib.util
import json
import os
import sys
import types
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import pandas as pd


UNKNOWN = "unknown"
DMC_FIELDS = [
    "session",
    "regime",
    "regime_snapshot_id",
    "structure_state",
    "volatility_state",
]
DMC_AUDIT_COLUMNS = [
    "dmc_label_confidence",
    "dmc_label_source",
    "dmc_label_version",
]
DMC_LABEL_SOURCE = "dmc_bridge_v1"
DMC_LABEL_VERSION = "1.0"


@dataclass
class DMCBridgeOptions:
    """Configuration for DMC label backfill."""

    input_path: str
    output_path: str
    dmc_root: str = "/mnt/c/Users/12645/DMC-Sisie-Quantive"
    snapshot_granularity: str = "week"
    overwrite: bool = False
    preserve_original_columns: bool = True
    audit_report_path: Optional[str] = None
    fields: list[str] = field(default_factory=lambda: DMC_FIELDS.copy())
    symbol_4h_paths: Optional[dict[str, str]] = None


def backfill_with_dmc(options: DMCBridgeOptions) -> pd.DataFrame:
    """Backfill SSS label fields by calling local DMC enrichers."""
    if options.snapshot_granularity not in {"day", "week", "month"}:
        raise ValueError("snapshot_granularity must be one of: day, week, month")
    invalid_fields = sorted(set(options.fields) - set(DMC_FIELDS))
    if invalid_fields:
        raise ValueError(f"Unsupported DMC bridge fields: {invalid_fields}")
    if not os.path.exists(options.input_path):
        raise FileNotFoundError(f"Input CSV not found: {options.input_path}")

    df = pd.read_csv(options.input_path)
    _validate_input_columns(df)
    result, stats = apply_dmc_labels(df, options)
    result = _add_dmc_audit_columns(result, options, stats)

    os.makedirs(os.path.dirname(options.output_path) or ".", exist_ok=True)
    result.to_csv(options.output_path, index=False)

    report_path = options.audit_report_path or _default_audit_report_path(options.output_path)
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(build_dmc_bridge_report(options, stats, len(result)))
    return result


def apply_dmc_labels(df: pd.DataFrame, options: DMCBridgeOptions) -> tuple[pd.DataFrame, Dict[str, Dict[str, int]]]:
    """Apply DMC enrichers to a DataFrame and return the updated frame plus stats."""
    modules = _import_dmc_modules(options.dmc_root)
    trade_log = modules["trade_log"]
    engine = modules["engine"]

    symbol_4h_paths = options.symbol_4h_paths or default_symbol_4h_paths(options.dmc_root)
    _validate_parquet_runtime(symbol_4h_paths, options.fields)
    enrichers = [
        trade_log.RegimeEnricher(symbol_4h_paths, snapshot_granularity=options.snapshot_granularity),
        trade_log.SessionEnricher(),
        trade_log.StructureStateEnricher(symbol_4h_paths),
        trade_log.VolatilityEnricher(symbol_4h_paths),
    ]

    out = df.copy()
    for field_name in DMC_FIELDS:
        if field_name not in out.columns:
            out[field_name] = UNKNOWN
        if options.preserve_original_columns and field_name in options.fields:
            original_col = f"original_{field_name}"
            if original_col not in out.columns:
                out[original_col] = out[field_name]

    trades = [_row_to_trade_record(row, engine) for _, row in out.iterrows()]
    for enricher in enrichers:
        _call_dmc_safely(enricher.bulk_prepare, trades)

    stats = {
        field_name: {"filled": 0, "skipped_valid": 0, "missing": 0}
        for field_name in options.fields
    }

    for idx, trade in zip(out.index, trades):
        labels: dict[str, Any] = {}
        for enricher in enrichers:
            labels.update(_call_dmc_safely(enricher.enrich, trade))

        for field_name in options.fields:
            current = out.at[idx, field_name]
            if not options.overwrite and not is_missing(current):
                stats[field_name]["skipped_valid"] += 1
                continue

            value = labels.get(field_name, UNKNOWN)
            if is_missing(value):
                stats[field_name]["missing"] += 1
                continue

            out.at[idx, field_name] = value
            stats[field_name]["filled"] += 1

    return out, stats


def default_symbol_4h_paths(dmc_root: str) -> dict[str, str]:
    """Return the default DMC 4H parquet paths for supported symbols."""
    data_dir = os.path.join(dmc_root, "data")
    return {
        "BTCUSDT": os.path.join(data_dir, "binance_BTCUSDT_4h.parquet"),
        "ETHUSDT": os.path.join(data_dir, "binance_ETHUSDT_4h.parquet"),
        "BTC": os.path.join(data_dir, "binance_BTCUSDT_4h.parquet"),
        "ETH": os.path.join(data_dir, "binance_ETHUSDT_4h.parquet"),
    }


def parse_symbol_4h_paths(values: Optional[Iterable[str]]) -> Optional[dict[str, str]]:
    """Parse CLI values like BTCUSDT=path/to/file.parquet."""
    if not values:
        return None
    parsed = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid --symbol-4h-path value: {item}")
        symbol, path = item.split("=", 1)
        parsed[symbol.strip().upper()] = path.strip()
    return parsed


def _validate_parquet_runtime(symbol_4h_paths: dict[str, str], fields: list[str]) -> None:
    """Raise a clear error when DMC parquet labels need a missing parquet engine."""
    parquet_fields = {"regime", "regime_snapshot_id", "structure_state", "volatility_state"}
    if not parquet_fields.intersection(fields):
        return
    needs_parquet = any(str(path).lower().endswith(".parquet") and os.path.exists(path)
                        for path in symbol_4h_paths.values())
    if not needs_parquet:
        return
    if importlib.util.find_spec("pyarrow") is None and importlib.util.find_spec("fastparquet") is None:
        raise RuntimeError(
            "DMC bridge needs pyarrow or fastparquet to read DMC 4H parquet data. "
            "Install project requirements or run: pip install pyarrow"
        )


def _call_dmc_safely(func, *args):
    """Call DMC code while isolating console output encoding issues."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args)


def is_missing(value: Any) -> bool:
    """Return True when a label value is effectively missing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    return str(value).strip().lower() in {"", "unknown", "nan", "none"}


def _add_dmc_audit_columns(
    result: pd.DataFrame,
    options: DMCBridgeOptions,
    stats: Dict[str, Dict[str, int]],
) -> pd.DataFrame:
    """Add dmc_label_confidence, dmc_label_source, dmc_label_version audit columns.

    dmc_label_confidence per field per row (JSON):
      direct  — DMC enricher computed this label directly
      derived — label was derived from another label (e.g. structure_state v1 ← regime)
      none    — DMC could not provide this label (value = unknown)
    """
    out = result.copy()

    # dmc_label_source and dmc_label_version are constant across all rows
    out["dmc_label_source"] = DMC_LABEL_SOURCE
    out["dmc_label_version"] = DMC_LABEL_VERSION

    # Compute per-row confidence JSON
    confidences = []
    for idx, row in out.iterrows():
        row_conf = {}
        for field_name in options.fields:
            value = row.get(field_name, UNKNOWN)
            if is_missing(value):
                row_conf[field_name] = "none"
            elif field_name == "structure_state":
                # v2: structure_state is independently computed by ADX → direct
                # v1 legacy marker: if structure_state == regime, it was derived
                regime_val = row.get("regime", UNKNOWN)
                if not is_missing(value) and not is_missing(regime_val) and str(value) == str(regime_val):
                    row_conf[field_name] = "derived"
                else:
                    row_conf[field_name] = "direct"
            else:
                # session, regime, regime_snapshot_id, volatility_state are always direct
                row_conf[field_name] = "direct"
        confidences.append(json.dumps(row_conf, ensure_ascii=False))

    out["dmc_label_confidence"] = confidences
    return out


def build_dmc_bridge_report(options: DMCBridgeOptions, stats: Dict[str, Dict[str, int]], rows: int) -> str:
    """Build a small Markdown audit report for DMC bridge backfill."""
    lines = [
        "# DMC Bridge Audit Report",
        "",
        f"- generated_at_utc: `{datetime.utcnow().isoformat()}Z`",
        f"- input_path: `{options.input_path}`",
        f"- output_path: `{options.output_path}`",
        f"- dmc_root: `{options.dmc_root}`",
        f"- rows: {rows}",
        f"- snapshot_granularity: `{options.snapshot_granularity}`",
        f"- overwrite: `{options.overwrite}`",
        "",
        "## Field Stats",
        "",
        "| Field | Filled | Skipped Valid | Missing |",
        "|-------|--------|---------------|---------|",
    ]
    for field_name in options.fields:
        item = stats.get(field_name, {})
        lines.append(
            f"| {field_name} | {item.get('filled', 0)} | "
            f"{item.get('skipped_valid', 0)} | {item.get('missing', 0)} |"
        )
    lines.extend([
        "",
        "## Audit Columns",
        "",
        f"- `dmc_label_source`: `{DMC_LABEL_SOURCE}`",
        f"- `dmc_label_version`: `{DMC_LABEL_VERSION}`",
        "- `dmc_label_confidence`: JSON map per row (direct/derived/none per field)",
        "",
        "## Scope",
        "",
        "- Uses DMC local backtest enrichers for session/regime/structure/volatility labels.",
        "- Does not backfill OI, funding, CVD, ETF, macro, or Coinbase premium fields.",
        "- Original field values are preserved in `original_*` columns when enabled.",
    ])
    return "\n".join(lines)


def _validate_input_columns(df: pd.DataFrame) -> None:
    required = ["trade_id", "strategy_name", "symbol", "direction", "entry_time", "exit_time", "pnl_R", "pnl_usd"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for DMC bridge: {missing}")


def _import_dmc_modules(dmc_root: str) -> dict[str, Any]:
    if not os.path.isdir(dmc_root):
        raise FileNotFoundError(f"DMC root not found: {dmc_root}")

    removed = {}
    for name in ["trade_engine.trade_log", "trade_engine.engine", "trade_engine", "strategies"]:
        if name in sys.modules:
            removed[name] = sys.modules.pop(name)

    try:
        package = types.ModuleType("trade_engine")
        package.__path__ = [os.path.join(dmc_root, "trade_engine")]
        sys.modules["trade_engine"] = package

        # Register strategies module (needed by trade_log → indicators import)
        strategies = types.ModuleType("strategies")
        strategies.__path__ = [os.path.join(dmc_root, "strategies")]
        sys.modules["strategies"] = strategies

        engine = _load_dmc_module(
            "trade_engine.engine",
            os.path.join(dmc_root, "trade_engine", "engine.py"),
        )
        trade_log = _load_dmc_module(
            "trade_engine.trade_log",
            os.path.join(dmc_root, "trade_engine", "trade_log.py"),
        )
    except Exception:
        for name, module in removed.items():
            sys.modules[name] = module
        raise

    return {"engine": engine, "trade_log": trade_log}


def _load_dmc_module(module_name: str, file_path: str) -> Any:
    """Load a DMC module by file path without executing package __init__."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"DMC module file not found: {file_path}")
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load DMC module: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _row_to_trade_record(row: pd.Series, engine_module: Any) -> Any:
    side = _direction_to_order_side(row.get("direction"), engine_module.OrderSide)
    return engine_module.TradeRecord(
        entry_time=pd.to_datetime(row["entry_time"]),
        exit_time=pd.to_datetime(row["exit_time"]),
        side=side,
        total_pnl=float(row.get("pnl_usd", 0.0)),
        strategy_id=str(row.get("strategy_name", UNKNOWN)),
        symbol=str(row.get("symbol", UNKNOWN)).upper(),
    )


def _direction_to_order_side(direction: Any, order_side: Any) -> Any:
    text = str(direction).strip().lower()
    if text == "long":
        return order_side.LONG
    if text == "short":
        return order_side.SHORT
    raise ValueError(f"Unsupported direction for DMC bridge: {direction}")


def _default_audit_report_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return f"{base}_dmc_bridge_report.md"


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser for DMC bridge."""
    parser = argparse.ArgumentParser(description="Backfill SSS labels using local DMC enrichers.")
    parser.add_argument("--input", required=True, dest="input_path", help="Input SSS CSV path.")
    parser.add_argument("--output", required=True, dest="output_path", help="Output CSV path.")
    parser.add_argument("--dmc-root", default="/mnt/c/Users/12645/DMC-Sisie-Quantive", help="Local DMC project root.")
    parser.add_argument("--snapshot-granularity", choices=["day", "week", "month"], default="week")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing non-unknown labels.")
    parser.add_argument(
        "--no-preserve-original",
        action="store_false",
        dest="preserve_original_columns",
        help="Do not create original_* audit columns.",
    )
    parser.add_argument("--audit-report", default=None, dest="audit_report_path")
    parser.add_argument(
        "--fields",
        nargs="+",
        default=DMC_FIELDS.copy(),
        help="Fields to backfill. Default: all DMC-supported label fields.",
    )
    parser.add_argument(
        "--symbol-4h-path",
        action="append",
        default=None,
        help="Override 4H data path, e.g. BTCUSDT=C:/path/binance_BTCUSDT_4h.parquet.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    options = DMCBridgeOptions(
        input_path=args.input_path,
        output_path=args.output_path,
        dmc_root=args.dmc_root,
        snapshot_granularity=args.snapshot_granularity,
        overwrite=args.overwrite,
        preserve_original_columns=args.preserve_original_columns,
        audit_report_path=args.audit_report_path,
        fields=args.fields,
        symbol_4h_paths=parse_symbol_4h_paths(args.symbol_4h_path),
    )
    result = backfill_with_dmc(options)
    print(json.dumps({
        "status": "ok",
        "output_path": options.output_path,
        "rows": len(result),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
