"""
Schema definitions for Strategy Enable Score System v1.1.
Defines all expected CSV fields and their metadata.
"""

# Core required fields
CORE_FIELDS = [
    "trade_id",
    "strategy_name",
    "symbol",
    "direction",
    "entry_time",
    "exit_time",
    "pnl_R",
    "session",
    "regime",
]

# Optional but expected fields (filled with defaults if missing)
OPTIONAL_FIELDS = [
    "pnl_usd",
    "setup_type",
]

# Status / state fields (filled with 'unknown' if missing)
STATUS_FIELDS = [
    "volatility_state",
    "oi_state",
    "cvd_state",
    "funding_state",
    "coinbase_premium_state",
    "etf_flow_state",
]

# v1.1 layered regime fields
LAYERED_REGIME_FIELDS = [
    "regime_snapshot_id",
    "structure_state",
    "volatility_state",  # overlaps with STATUS_FIELDS
    "orderflow_state",
    "macro_state",
]

# DMC bridge audit columns (informational, not used for scoring)
DMC_AUDIT_FIELDS = [
    "dmc_label_confidence",
    "dmc_label_source",
    "dmc_label_version",
]

# All fields that should exist in the output DataFrame
ALL_EXPECTED_FIELDS = sorted(set(
    CORE_FIELDS + OPTIONAL_FIELDS + STATUS_FIELDS
    + ["regime_snapshot_id", "structure_state", "orderflow_state", "macro_state"]
    + DMC_AUDIT_FIELDS
))


def validate_direction(value: str) -> bool:
    """Check if direction is valid."""
    return str(value).lower() in ("long", "short")


def validate_trade_id(trade_id: str) -> bool:
    """Check if trade_id is non-empty."""
    return bool(trade_id) and str(trade_id).strip() != ""
