"""
Data Loader for Strategy Enable Score System v1.1.
Reads CSV trade logs, validates fields, standardizes types, applies filters.
"""

import os
import warnings
import pandas as pd
from typing import List

from .schemas import CORE_FIELDS, STATUS_FIELDS, ALL_EXPECTED_FIELDS
from .config import SSSConfig


def load_trades(config: SSSConfig) -> pd.DataFrame:
    """Load and validate trade CSV files.
    
    Args:
        config: Validated SSSConfig object.
    
    Returns:
        pd.DataFrame: Standardized trades with all expected fields.
    
    Raises:
        FileNotFoundError: If any CSV path doesn't exist.
        ValueError: If core fields are missing, pnl_R is non-numeric,
                    or time fields are invalid.
    """
    dfs = []
    for path in config.input_path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"CSV file not found: {path}")
        df = pd.read_csv(path)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)
    return _standardize(df, config)


def _standardize(df: pd.DataFrame, config: SSSConfig) -> pd.DataFrame:
    """Apply full validation and standardization pipeline."""
    
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()
    
    # 1. Validate core fields exist
    missing_core = [f for f in CORE_FIELDS if f not in df.columns]
    if missing_core:
        raise ValueError(f"Missing core fields: {missing_core}")

    # 2. Validate regime field
    if config.validation.require_exit_after_entry:
        missing_regime = df["regime"].isna()
        if missing_regime.any():
            rows = df[missing_regime].index.tolist()
            raise ValueError(f"Missing 'regime' values at rows: {rows}")

    # 3. Validate pnl_R is numeric
    pnl = pd.to_numeric(df["pnl_R"], errors="coerce")
    bad_pnl = pnl.isna()
    if bad_pnl.any():
        rows = df[bad_pnl].index.tolist()
        raise ValueError(f"Non-numeric pnl_R at rows: {rows}")
    df["pnl_R"] = pnl

    # 4. Validate and parse time fields
    for time_col in ["entry_time", "exit_time"]:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        bad_time = df[time_col].isna()
        if bad_time.any():
            rows = df[bad_time].index.tolist()
            raise ValueError(f"Cannot parse '{time_col}' at rows: {rows}")

    # 5. Check exit_time >= entry_time
    if config.validation.require_exit_after_entry:
        bad_order = df["exit_time"] < df["entry_time"]
        if bad_order.any():
            rows = df[bad_order].index.tolist()
            raise ValueError(f"exit_time < entry_time at rows: {rows}")

    # 6. Check duplicate trade_id
    dup_mask = df.duplicated(subset="trade_id", keep=False)
    if dup_mask.any():
        dup_ids = df.loc[dup_mask, "trade_id"].unique().tolist()
        msg = f"Duplicate trade_id found: {dup_ids}"
        if config.validation.duplicate_trade_id == "error":
            raise ValueError(msg)
        elif config.validation.duplicate_trade_id == "warning":
            warnings.warn(msg)

    # 7. Validate direction
    df["direction"] = df["direction"].str.strip().str.lower()
    invalid_dir = ~df["direction"].isin(["long", "short"])
    if invalid_dir.any():
        rows = df[invalid_dir].index.tolist()
        raise ValueError(f"Invalid direction values at rows: {rows}. Must be 'long' or 'short'.")

    # 8. Fill missing optional fields
    fill_val = config.validation.fill_missing_state_with
    if "pnl_usd" not in df.columns:
        df["pnl_usd"] = 0.0
    else:
        df["pnl_usd"] = pd.to_numeric(df["pnl_usd"], errors="coerce").fillna(0.0)
        if df["pnl_usd"].isna().any():
            warnings.warn("Some pnl_usd values could not be parsed, filled with 0.0")

    # 9. Fill missing status fields
    for field in STATUS_FIELDS:
        if field not in df.columns:
            df[field] = fill_val
        else:
            df[field] = df[field].fillna(fill_val)

    # 10. Fill v1.1 layered regime fields
    for field in ["regime_snapshot_id", "structure_state", "orderflow_state", "macro_state"]:
        if field not in df.columns:
            df[field] = fill_val
        else:
            df[field] = df[field].fillna(fill_val)

    # 11. Fill optional setup_type
    if "setup_type" not in df.columns:
        df["setup_type"] = fill_val
    else:
        df["setup_type"] = df["setup_type"].fillna(fill_val)

    # 12. Fill volatility_state if also in layered (already handled)
    if "volatility_state" not in df.columns:
        df["volatility_state"] = fill_val
    else:
        df["volatility_state"] = df["volatility_state"].fillna(fill_val)

    # 13. Fill regime_snapshot_id
    if "regime_snapshot_id" not in df.columns:
        df["regime_snapshot_id"] = fill_val
    else:
        df["regime_snapshot_id"] = df["regime_snapshot_id"].fillna(fill_val)

    # 14. Apply filters
    df = _apply_filters(df, config)

    # 15. Ensure all expected columns exist in output
    for field in ALL_EXPECTED_FIELDS:
        if field not in df.columns:
            df[field] = fill_val

    # Sort by entry_time for consistent processing
    df = df.sort_values("entry_time").reset_index(drop=True)

    return df


def _apply_filters(df: pd.DataFrame, config: SSSConfig) -> pd.DataFrame:
    """Apply optional symbol, strategy, and date range filters."""
    f = config.filters

    if f.symbol:
        df = df[df["symbol"].isin(f.symbol)]
        if len(df) == 0:
            raise ValueError(f"No trades remain after symbol filter: {f.symbol}")

    if f.strategy_name:
        df = df[df["strategy_name"].isin(f.strategy_name)]
        if len(df) == 0:
            raise ValueError(f"No trades remain after strategy filter: {f.strategy_name}")

    if f.date_start:
        start = pd.Timestamp(f.date_start)
        df = df[df["entry_time"] >= start]
        if len(df) == 0:
            raise ValueError(f"No trades remain after date_start filter: {f.date_start}")

    if f.date_end:
        end = pd.Timestamp(f.date_end)
        df = df[df["entry_time"] <= end]
        if len(df) == 0:
            raise ValueError(f"No trades remain after date_end filter: {f.date_end}")

    return df
