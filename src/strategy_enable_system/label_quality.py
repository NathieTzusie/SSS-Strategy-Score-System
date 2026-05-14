"""
Label Quality Tool for Strategy Enable Score System v1.1 (P2-2).

Fixes common data quality issues in trade log CSVs:
- Backfills session from entry_time (UTC hour rules)
- Backfills structure_state from regime
- Normalizes regime_snapshot_id to {regime}_{YYYYMMDD}
- Generates a label quality report

Run standalone:
  PYTHONPATH=src python -m strategy_enable_system.label_quality --config config.yaml
"""

import os
import sys
import argparse
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict

from .config import load_config, SSSConfig, LabelQualityConfig

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Fields considered "missing" when they are NaN, empty string, or "unknown"
_MISSING_VALUES = {None, "", "unknown", "Unknown", "UNKNOWN"}


def is_missing(val) -> bool:
    """Check if a value should be treated as missing/unknown."""
    if val is None:
        return True
    if pd.isna(val):
        return True
    return str(val).strip().lower() in {"", "unknown"}


def classify_session(entry_dt: datetime, rules: dict) -> str:
    """Classify a UTC datetime into a session label.
    
    Uses fixed priority order to handle overlapping time ranges:
    1. weekend (Friday 21:00 UTC – Sunday 22:00 UTC)
    2. overlap (12:00–16:00 UTC) — London + NY
    3. Asia (00:00–09:00 UTC)
    4. London (07:00–16:00 UTC, non-overlap hours)
    5. NY (12:00–21:00 UTC, non-overlap hours)
    6. Off (fallback)
    """
    weekday = entry_dt.weekday()  # Monday=0, Sunday=6
    hour = entry_dt.hour
    minute = entry_dt.minute
    day_time = hour + minute / 60.0  # fractional hour
    
    # Weekend: Friday 21:00 – Sunday 22:00 UTC
    if weekday == 4 and day_time >= 21.0:
        return "weekend"
    if weekday == 5:  # Saturday
        return "weekend"
    if weekday == 6 and day_time < 22.0:  # Sunday before 22:00
        return "weekend"
    
    # Overlap: London + NY, 12:00–16:00 UTC
    if 12 <= day_time < 16:
        return "overlap"
    
    # Asia: 00:00–09:00 UTC
    if 0 <= day_time < 9:
        return "Asia"
    
    # London: 07:00–16:00 UTC (non-overlap: 07:00–12:00)
    if 7 <= day_time < 16:
        return "London"
    
    # NY: 12:00–21:00 UTC (non-overlap: 16:00–21:00)
    if 12 <= day_time < 21:
        return "NY"
    
    # Fallback
    return "Off"


def normalize_snapshot(regime: str, entry_dt: datetime, fmt: str) -> str:
    """Generate a normalized regime_snapshot_id from regime and entry_time."""
    date_str = entry_dt.strftime("%Y%m%d")
    return fmt.replace("{regime}", str(regime)).replace("{YYYYMMDD}", date_str)


# ============================================================
# P2-5: Quality Score / Readiness
# ============================================================

_FIELD_DISPLAY_NAMES = {
    "session": "Session",
    "structure_state": "Structure State",
    "volatility_state": "Volatility State",
    "orderflow_state": "Orderflow State",
    "macro_state": "Macro State",
}


def compute_field_quality(df: pd.DataFrame, field: str, fixes: dict) -> dict:
    """Compute quality metrics for a single field."""
    total = len(df)
    unknown_count = df[field].apply(is_missing).sum() if field in df.columns else total
    ratio = unknown_count / total if total > 0 else 1.0
    score = 100.0 - ratio * 100.0
    
    fixed_key = f"{field}_fixed"
    fixed = fixes.get(fixed_key, 0)
    
    return {
        "field": field,
        "total_rows": total,
        "unknown_after": unknown_count,
        "unknown_ratio_after": round(ratio, 4),
        "quality_score_after": round(score, 1),
        "fixed_count": fixed,
    }


def classify_readiness(unknown_ratio: float, config: "ReadinessConfig") -> str:
    """Classify a field's readiness status."""
    if unknown_ratio > config.unknown_blocking_threshold:
        return "BLOCK"
    elif unknown_ratio > config.unknown_warning_threshold:
        return "WARN"
    return "PASS"


def compute_snapshot_granularity(original_df: pd.DataFrame, fixed_df: pd.DataFrame, config) -> dict:
    """Diagnose regime_snapshot_id granularity."""
    total = len(fixed_df)
    
    orig_unique = original_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in original_df.columns else 0
    fixed_unique = fixed_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in fixed_df.columns else 0
    
    orig_ratio = orig_unique / total if total > 0 else 0
    fixed_ratio = fixed_unique / total if total > 0 else 0
    avg_trades = total / fixed_unique if fixed_unique > 0 else 0
    
    r = config.readiness
    diagnosis = "PASS"
    reasons = []
    
    if fixed_ratio > r.snapshot_unique_ratio_too_high:
        diagnosis = "WARN"
        reasons.append(f"unique_ratio={fixed_ratio:.2%} > {r.snapshot_unique_ratio_too_high:.0%}（过度碎片化）")
    if fixed_ratio < r.snapshot_unique_ratio_too_low and fixed_unique > 1:
        diagnosis = "WARN"
        reasons.append(f"unique_ratio={fixed_ratio:.2%} < {r.snapshot_unique_ratio_too_low:.0%}（粒度过粗）")
    if avg_trades < r.snapshot_min_avg_trades_per_snapshot:
        if diagnosis == "PASS":
            diagnosis = "WARN"
        reasons.append(f"avg_trades_per_snapshot={avg_trades:.1f} < {r.snapshot_min_avg_trades_per_snapshot}（每 snapshot 平均样本太少）")
    
    return {
        "unique_count_before": orig_unique,
        "unique_count_after": fixed_unique,
        "unique_ratio_before": round(orig_ratio, 4),
        "unique_ratio_after": round(fixed_ratio, 4),
        "average_trades_per_snapshot_after": round(avg_trades, 1),
        "diagnosis": diagnosis,
        "reasons": reasons,
    }


def compute_readiness(field_qualities: dict, snapshot_diag: dict, config) -> dict:
    """Compute P2 feature readiness levels."""
    
    def _worst(fields):
        statuses = []
        for f in fields:
            if f in field_qualities:
                statuses.append(field_qualities[f]["readiness_status"])
        if "BLOCK" in statuses:
            return "BLOCK"
        if "WARN" in statuses:
            return "WARN"
        return "PASS"
    
    # classifier: needs structure_state, volatility_state, orderflow_state, macro_state
    classifier_fields = ["structure_state", "volatility_state", "orderflow_state", "macro_state"]
    classifier = _worst(classifier_fields)
    
    # market_opportunity: needs volatility_state, orderflow_state, macro_state
    mo_fields = ["volatility_state", "orderflow_state", "macro_state"]
    mo = _worst(mo_fields)
    
    # layered_regime: needs structure_state + all layered + snapshot granularity
    layered = _worst(classifier_fields)
    if layered == "PASS" and snapshot_diag["diagnosis"] == "WARN":
        layered = "WARN"
    
    def _reason(status, desc):
        if status == "PASS":
            return f"所有必要字段 quality_score ≥ {100 - config.readiness.unknown_warning_threshold * 100:.0f}"
        elif status == "WARN":
            return f"部分字段存在 {config.readiness.unknown_warning_threshold:.0%}–{config.readiness.unknown_blocking_threshold:.0%} unknown"
        return f"关键字段 unknown > {config.readiness.unknown_blocking_threshold:.0%}"
    
    def _recommendation(status):
        if status == "PASS":
            return "可以进入下一阶段，但仍需人工抽检"
        elif status == "WARN":
            return "可以探索，但不建议作为自动化决策依据"
        return "不建议进入该功能，应先修复标签"
    
    return {
        "automatic_regime_classifier": {
            "readiness": classifier,
            "reason": _reason(classifier, "classifier"),
            "recommendation": _recommendation(classifier),
        },
        "market_opportunity_score": {
            "readiness": mo,
            "reason": _reason(mo, "market_opportunity"),
            "recommendation": _recommendation(mo),
        },
        "layered_regime_analysis": {
            "readiness": layered,
            "reason": _reason(layered, "layered") + ("；snapshot 粒度需要关注" if snapshot_diag.get("reasons") else ""),
            "recommendation": _recommendation(layered),
        },
    }


def compute_all_field_qualities(original_df: pd.DataFrame, fixed_df: pd.DataFrame, fixes: dict, config) -> dict:
    """Compute quality scores for all monitored fields."""
    fields = ["session", "structure_state", "volatility_state", "orderflow_state", "macro_state"]
    results = {}
    for f in fields:
        q = compute_field_quality(fixed_df, f, fixes)
        if f in original_df.columns:
            orig_unk = original_df[f].apply(is_missing).sum()
            q["unknown_before"] = orig_unk
            q["unknown_ratio_before"] = round(orig_unk / len(original_df), 4) if len(original_df) > 0 else 1.0
            q["quality_score_before"] = round(100.0 - q["unknown_ratio_before"] * 100.0, 1)
        else:
            q["unknown_before"] = q["unknown_after"]
            q["unknown_ratio_before"] = q["unknown_ratio_after"]
            q["quality_score_before"] = q["quality_score_after"]
        q["readiness_status"] = classify_readiness(q["unknown_ratio_after"], config.readiness)
        results[f] = q
    return results


def fix_labels(df: pd.DataFrame, config: LabelQualityConfig):
    """Apply all label fixes to a DataFrame and return fix counts."""
    fixes: Dict[str, int] = {}

    # --- Session backfill ---
    sb = config.session_backfill
    fixes["session_fixed"] = 0
    fixes["session_skipped"] = 0
    
    if sb.enabled and "entry_time" in df.columns:
        df["entry_time_dt"] = pd.to_datetime(df["entry_time"])
        
        for idx in df.index:
            current = df.at[idx, "session"]
            if not sb.overwrite_existing and not is_missing(current):
                fixes["session_skipped"] += 1
                continue
            entry_dt = df.at[idx, "entry_time_dt"]
            df.at[idx, "session"] = classify_session(entry_dt, sb.rules)
            fixes["session_fixed"] += 1
        
        df.drop(columns=["entry_time_dt"], inplace=True, errors="ignore")

    # --- Structure state backfill ---
    ss = config.structure_state_backfill
    fixes["structure_state_fixed"] = 0
    fixes["structure_state_skipped"] = 0
    
    if ss.enabled:
        src_field = ss.source_field
        for idx in df.index:
            current = df.at[idx, "structure_state"] if "structure_state" in df.columns else None
            if not ss.overwrite_existing and not is_missing(current):
                fixes["structure_state_skipped"] += 1
                continue
            src_val = df.at[idx, src_field] if src_field in df.columns else None
            if not is_missing(src_val):
                df.at[idx, "structure_state"] = src_val
                fixes["structure_state_fixed"] += 1

    # --- Regime snapshot normalization ---
    sn = config.regime_snapshot_normalization
    fixes["snapshot_normalized"] = 0
    orig_col = sn.preserve_original_column
    
    if sn.enabled and "entry_time" in df.columns and "regime" in df.columns:
        # Preserve originals
        if config.preserve_original_regime_snapshot_id and orig_col and orig_col not in df.columns:
            df[orig_col] = df["regime_snapshot_id"] if "regime_snapshot_id" in df.columns else None
        
        entry_dts = pd.to_datetime(df["entry_time"])
        for idx in df.index:
            current = df.at[idx, "regime_snapshot_id"] if "regime_snapshot_id" in df.columns else None
            # Skip if overwrite is off and value doesn't look fragmented
            # Fragmented = high-uniqueness old format like trend_up_uu_2025052917
            if not sn.overwrite_existing and not is_missing(current):
                # Check if looks like fragmented format (has hour-level detail or too long)
                current_str = str(current)
                # Skip if already looks normalized (contains regime prefix + _W or _YYYYMMDD)
                if len(current_str.split("_")) <= 3:
                    continue  # already reasonable format
            
            regime = df.at[idx, "regime"]
            df.at[idx, "regime_snapshot_id"] = normalize_snapshot(regime, entry_dts[idx], sn.format)
            fixes["snapshot_normalized"] += 1

    return fixes


def build_quality_report(original_df: pd.DataFrame, fixed_df: pd.DataFrame, fixes: dict,
                         config: LabelQualityConfig, field_qualities: dict = None,
                         snapshot_diag: dict = None, readiness: dict = None) -> str:
    """Generate a Markdown label quality report."""
    lines: List[str] = []
    
    def h(lvl, text):
        lines.append(f"{'#' * lvl} {text}")
    
    h(1, "Label Quality Report")
    lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**原始交易数：** {len(original_df)}")
    lines.append(f"**修复后交易数：** {len(fixed_df)}")
    lines.append("")
    
    # Session
    h(2, "Session 回填")
    orig_unknown = original_df["session"].apply(is_missing).sum() if "session" in original_df.columns else 0
    fixed_unknown = fixed_df["session"].apply(is_missing).sum() if "session" in fixed_df.columns else 0
    lines.append(f"- 修复前 unknown：{orig_unknown}/{len(original_df)} ({orig_unknown/len(original_df)*100:.1f}%)")
    lines.append(f"- 修复后 unknown：{fixed_unknown}/{len(fixed_df)} ({fixed_unknown/len(fixed_df)*100:.1f}%)")
    lines.append(f"- 实际回填：{fixes.get('session_fixed', 0)} 笔")
    if fixes.get("session_skipped", 0) > 0:
        lines.append(f"- 已有有效值跳过：{fixes.get('session_skipped', 0)} 笔")
    
    if fixed_unknown == 0:
        lines.append(f"\n**✅ session 字段已全部修复。**")
    lines.append("")
    
    # Structure state
    h(2, "Structure State 回填")
    orig_ss_unknown = original_df["structure_state"].apply(is_missing).sum() if "structure_state" in original_df.columns else 0
    fixed_ss_unknown = fixed_df["structure_state"].apply(is_missing).sum() if "structure_state" in fixed_df.columns else 0
    lines.append(f"- 修复前 unknown：{orig_ss_unknown}/{len(original_df)} ({orig_ss_unknown/len(original_df)*100:.1f}%)")
    lines.append(f"- 修复后 unknown：{fixed_ss_unknown}/{len(fixed_df)} ({fixed_ss_unknown/len(fixed_df)*100:.1f}%)")
    lines.append(f"- 实际回填：{fixes.get('structure_state_fixed', 0)} 笔（来源：`{config.structure_state_backfill.source_field}`）")
    
    if fixed_ss_unknown == 0:
        lines.append(f"\n**✅ structure_state 字段已全部修复。**")
    lines.append("")
    
    # Regime snapshot
    h(2, "Regime Snapshot ID 规范化")
    orig_unique = original_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in original_df.columns else 0
    fixed_unique = fixed_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in fixed_df.columns else 0
    lines.append(f"- 修复前 unique 数：{orig_unique}")
    lines.append(f"- 修复后 unique 数：{fixed_unique}")
    lines.append(f"- 格式：`{config.regime_snapshot_normalization.format}`")
    
    if config.preserve_original_regime_snapshot_id:
        orig_col = config.regime_snapshot_normalization.preserve_original_column
        lines.append(f"- 原始值保留于：`{orig_col}`")
    
    lines.append(f"\n**✅ unique 数从 {orig_unique} → {fixed_unique}（下降 {(1-fixed_unique/orig_unique)*100:.0f}%）**")
    lines.append("")
    
    # Summary
    h(2, "修复汇总")
    lines.append(f"| 字段 | 修复数 | 说明 |")
    lines.append(f"|------|--------|------|")
    lines.append(f"| session | {fixes.get('session_fixed', 0)} | UTC 小时 → 交易时段 |")
    lines.append(f"| structure_state | {fixes.get('structure_state_fixed', 0)} | 来源：{config.structure_state_backfill.source_field} |")
    lines.append(f"| regime_snapshot_id | {fixes.get('snapshot_normalized', 0)} | 格式：{config.regime_snapshot_normalization.format} |")
    lines.append("")
    
    # --- P2-5: Field Quality Scores ---
    if field_qualities:
        h(2, "Field Quality Scores")
        lines.append("")
        lines.append("| Field | Unknown After | Unknown Ratio | Quality Score | Readiness |")
        lines.append("|-------|--------------|---------------|---------------|-----------|")
        for f in ["session", "structure_state", "volatility_state", "orderflow_state", "macro_state"]:
            if f in field_qualities:
                q = field_qualities[f]
                lines.append(
                    f"| {_FIELD_DISPLAY_NAMES.get(f, f)} "
                    f"| {q['unknown_after']}/{q['total_rows']} "
                    f"| {q['unknown_ratio_after']:.1%} "
                    f"| {q['quality_score_after']:.0f} "
                    f"| {q['readiness_status']} |"
                )
        lines.append("")
    
    # --- P2-5: Snapshot Granularity ---
    if snapshot_diag:
        h(2, "Regime Snapshot Granularity")
        lines.append("")
        lines.append(f"- Unique count: {snapshot_diag['unique_count_before']} → {snapshot_diag['unique_count_after']}")
        lines.append(f"- Unique ratio: {snapshot_diag['unique_ratio_before']:.1%} → {snapshot_diag['unique_ratio_after']:.1%}")
        lines.append(f"- Avg trades per snapshot: {snapshot_diag['average_trades_per_snapshot_after']:.1f}")
        lines.append(f"- Diagnosis: **{snapshot_diag['diagnosis']}**")
        if snapshot_diag.get("reasons"):
            for reason in snapshot_diag["reasons"]:
                lines.append(f"  - {reason}")
        lines.append("")
    
    # --- P2-5: P2 Readiness ---
    if readiness:
        h(2, "P2 Readiness")
        lines.append("")
        lines.append("| Feature | Readiness | Reason | Recommendation |")
        lines.append("|---------|-----------|--------|----------------|")
        for feature_key, display in [
            ("automatic_regime_classifier", "Automatic Regime Classifier"),
            ("market_opportunity_score", "Market Opportunity Score"),
            ("layered_regime_analysis", "Layered Regime Analysis"),
        ]:
            info = readiness.get(feature_key, {})
            lines.append(
                f"| {display} "
                f"| {info.get('readiness', '?')} "
                f"| {info.get('reason', '')} "
                f"| {info.get('recommendation', '')} |"
            )
        lines.append("")
        lines.append("**Readiness 含义：**")
        lines.append("- **PASS**：可以进入下一阶段，但仍需人工抽检")
        lines.append("- **WARN**：可以探索，但不建议作为自动化决策依据")
        lines.append("- **BLOCK**：不建议进入该功能，应先修复标签")
        lines.append("")
    
    h(2, "风险提示")
    lines.append("- ⚠️ 本工具只做标签治理（session / structure_state / regime_snapshot_id），**不改变 pnl_R、trade_id、strategy_name、regime**")
    lines.append("- ⚠️ 本工具**不改变评分逻辑**，修复后重新运行 `main.py` 时 Enable Score 不变")
    lines.append("- ⚠️ 本工具**不覆盖原始 CSV**，输出为新文件")
    lines.append("- ⚠️ `structure_state` 直接复制自 `regime`，不推断复杂结构")
    lines.append("- ⚠️ 分层字段（volatility_state, orderflow_state, macro_state）不在本次修复范围，仍需上游数据管道填充")
    lines.append("")
    
    lines.append("*Generated by Strategy Enable Score System v1.1 — P2-2 Label Quality Tool*")
    
    return "\n".join(lines)


def build_quality_summary_csv(original_df: pd.DataFrame, fixed_df: pd.DataFrame, fixes: dict,
                              field_qualities: dict = None) -> pd.DataFrame:
    """Generate a CSV summary of label quality changes with quality scores."""
    rows = []
    
    fields = ["session", "structure_state", "volatility_state", "orderflow_state", "macro_state", "regime_snapshot_id"]
    
    for f in fields:
        total = len(fixed_df)
        if f == "regime_snapshot_id":
            orig_unk = original_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in original_df.columns else 0
            fixed_unk = fixed_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in fixed_df.columns else 0
            fixed_count = fixes.get("snapshot_normalized", 0)
            row = {
                "field": f, "total_rows": total,
                "unknown_before": orig_unk, "unknown_after": fixed_unk,
                "unknown_ratio_before": round(orig_unk / total, 4) if total > 0 else 0,
                "unknown_ratio_after": round(fixed_unk / total, 4) if total > 0 else 0,
                "fixed_count": fixed_count, "notes": "unique count"
            }
        else:
            orig_unk = original_df[f].apply(is_missing).sum() if f in original_df.columns else total
            fixed_unk = fixed_df[f].apply(is_missing).sum() if f in fixed_df.columns else total
            fixed_count = fixes.get(f"{f}_fixed", 0)
            row = {
                "field": f, "total_rows": total,
                "unknown_before": orig_unk, "unknown_after": fixed_unk,
                "unknown_ratio_before": round(orig_unk / total, 4) if total > 0 else 1.0,
                "unknown_ratio_after": round(fixed_unk / total, 4) if total > 0 else 1.0,
                "fixed_count": fixed_count, "notes": ""
            }
        
        # Add quality scores and readiness if available
        if field_qualities and f in field_qualities:
            q = field_qualities[f]
            row["quality_score_before"] = q.get("quality_score_before", None)
            row["quality_score_after"] = q.get("quality_score_after", None)
            row["readiness_status"] = q.get("readiness_status", "")
        else:
            if total > 0:
                row["quality_score_before"] = round(100.0 - row["unknown_ratio_before"] * 100.0, 1)
                row["quality_score_after"] = round(100.0 - row["unknown_ratio_after"] * 100.0, 1)
            else:
                row["quality_score_before"] = 0.0
                row["quality_score_after"] = 0.0
            row["readiness_status"] = ""
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def validate_required_columns(df: pd.DataFrame, required: List[str]):
    """Check required columns exist. Raises ValueError if missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def run(config_path: str, input_override: str = None, output_dir_override: str = None):
    """Main entry point for label quality tool.
    
    Args:
        config_path: Path to config YAML file.
        input_override: Optional path to override config.input_path (single CSV).
        output_dir_override: Optional path to override config.label_quality.output_dir.
    """
    logger.info(f"Loading config from {config_path}")
    config = load_config(config_path)
    
    lq = config.label_quality
    if not lq.enabled:
        logger.warning("label_quality.enabled is False. Set to true in config.yaml to run.")
        return
    
    # Apply overrides (CLI wins over config)
    if input_override:
        logger.info(f"[--input override] Using input: {input_override}")
        config.input_path = [input_override]
    if output_dir_override:
        logger.info(f"[--output-dir override] Using output_dir: {output_dir_override}")
        lq.output_dir = output_dir_override
    
    # Read original CSV(s)
    dfs = []
    for path in config.input_path:
        logger.info(f"Reading {path}")
        df = pd.read_csv(path)
        dfs.append(df)
    
    original_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"Loaded {len(original_df)} trades")
    
    # Validate required columns
    validate_required_columns(original_df, ["trade_id", "strategy_name", "regime", "entry_time"])
    
    # Work on a copy
    fixed_df = original_df.copy()
    
    # Apply fixes
    logger.info("Applying label fixes...")
    fixes = fix_labels(fixed_df, lq)
    
    # P2-5: Quality scores and readiness
    logger.info("Computing quality scores and readiness...")
    field_qualities = compute_all_field_qualities(original_df, fixed_df, fixes, lq)
    snapshot_diag = compute_snapshot_granularity(original_df, fixed_df, lq)
    readiness = compute_readiness(field_qualities, snapshot_diag, lq)
    
    logger.info(f"Readiness — classifier: {readiness['automatic_regime_classifier']['readiness']}, "
                f"market_opportunity: {readiness['market_opportunity_score']['readiness']}, "
                f"layered: {readiness['layered_regime_analysis']['readiness']}")
    
    # Output directory
    os.makedirs(lq.output_dir, exist_ok=True)
    
    # Write cleaned CSV
    cleaned_path = os.path.join(lq.output_dir, lq.cleaned_csv_name)
    fixed_df.to_csv(cleaned_path, index=False)
    logger.info(f"Cleaned CSV: {cleaned_path}")
    
    # Generate quality report
    report = build_quality_report(original_df, fixed_df, fixes, lq, field_qualities, snapshot_diag, readiness)
    report_path = os.path.join(lq.output_dir, "label_quality_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"Report: {report_path}")
    
    # Generate summary CSV
    summary_df = build_quality_summary_csv(original_df, fixed_df, fixes, field_qualities)
    summary_path = os.path.join(lq.output_dir, "label_quality_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    logger.info(f"Summary: {summary_path}")
    
    # Summary stats
    session_before = original_df["session"].apply(is_missing).sum()
    session_after = fixed_df["session"].apply(is_missing).sum()
    ss_before = original_df["structure_state"].apply(is_missing).sum() if "structure_state" in original_df.columns else 0
    ss_after = fixed_df["structure_state"].apply(is_missing).sum() if "structure_state" in fixed_df.columns else 0
    snap_before = original_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in original_df.columns else 0
    snap_after = fixed_df["regime_snapshot_id"].nunique() if "regime_snapshot_id" in fixed_df.columns else 0
    
    logger.info("=== Quality Changes ===")
    logger.info(f"session:        {session_before} → {session_after} unknown ({session_before - session_after} fixed)")
    logger.info(f"structure_state: {ss_before} → {ss_after} unknown ({ss_before - ss_after} fixed)")
    logger.info(f"snapshot unique: {snap_before} → {snap_after} (from {snap_before} to {snap_after})")
    logger.info("Done.")


def main():
    parser = argparse.ArgumentParser(
        description="Strategy Enable Score System v1.1 — Label Quality Tool"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml)",
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="Override config.input_path with a single CSV path (optional)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        dest="output_dir",
        help="Override config.label_quality.output_dir (optional)",
    )
    args = parser.parse_args()
    run(args.config, input_override=args.input, output_dir_override=args.output_dir)


if __name__ == "__main__":
    main()
