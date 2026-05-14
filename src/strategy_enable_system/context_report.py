"""
Partial Context Report for Strategy Enable Score System v1.1 (P2-14).

Generates a read-only informational report showing the distribution of external
market labels (OI, funding, ETF, session, structure, volatility) grouped by
strategy/regime.

INFORMATIONAL ONLY — does not modify Enable Score, status, or scoring logic.

Run standalone:
  PYTHONPATH=src python -m strategy_enable_system.context_report --config config.yaml
  PYTHONPATH=src python -m strategy_enable_system.context_report --config config.yaml --dry-run
"""

import os
import json
import argparse
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

from .config import load_config, PartialContextConfig

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Fields recognised as "missing" (null, NaN, empty, or literal "unknown")
_MISSING_VALUES = {None, "", "unknown", "Unknown", "UNKNOWN"}


def is_unknown(val) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    return str(val).strip().lower() in {"", "unknown"}


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------


def compute_field_distribution(df: pd.DataFrame, field: str,
                               min_coverage: float = 0.80) -> dict:
    """Compute distribution and coverage stats for one field.

    Returns a dict with keys:
        total_trades, known_count, unknown_count, coverage_rate,
        readiness_status, dominant_value, dominant_value_share,
        distribution_json
    """
    total = len(df)
    if total == 0:
        return {
            "total_trades": 0, "known_count": 0, "unknown_count": 0,
            "coverage_rate": 0.0, "readiness_status": "BLOCK",
            "dominant_value": "n/a", "dominant_value_share": 0.0,
            "distribution_json": "{}",
        }

    if field not in df.columns:
        return {
            "total_trades": total, "known_count": 0, "unknown_count": total,
            "coverage_rate": 0.0, "readiness_status": "BLOCK",
            "dominant_value": "n/a", "dominant_value_share": 0.0,
            "distribution_json": "{}",
        }

    unknown_mask = df[field].apply(is_unknown)
    unknown_count = int(unknown_mask.sum())
    known_count = total - unknown_count
    coverage = known_count / total if total > 0 else 0.0

    if coverage >= min_coverage:
        readiness = "PASS"
    elif coverage > 0:
        readiness = "WARN"
    else:
        readiness = "BLOCK"

    # Dominant value
    if known_count > 0:
        value_counts = df.loc[~unknown_mask, field].value_counts()
        dominant_value = str(value_counts.index[0])
        dominant_share = float(value_counts.iloc[0]) / total
        # Build distribution dict as JSON-safe string
        dist_dict = {str(k): int(v) for k, v in value_counts.items()}
        distribution_json = json.dumps(dist_dict, ensure_ascii=False)
    else:
        dominant_value = "unknown"
        dominant_share = 0.0
        distribution_json = "{}"

    return {
        "total_trades": total,
        "known_count": known_count,
        "unknown_count": unknown_count,
        "coverage_rate": round(coverage, 4),
        "readiness_status": readiness,
        "dominant_value": dominant_value,
        "dominant_value_share": round(dominant_share, 4),
        "distribution_json": distribution_json,
    }


def build_context_summary(df: pd.DataFrame, config: PartialContextConfig) -> pd.DataFrame:
    """Build a structured context summary DataFrame, one row per (group, field)."""
    rows = []
    group_cols = config.group_by
    fields = config.fields

    if len(df) == 0:
        return pd.DataFrame()

    for group_keys, group_df in df.groupby(group_cols, observed=False):
        # Normalise group_keys to tuple
        if not isinstance(group_keys, tuple):
            group_keys = (group_keys,)

        for field in fields:
            dist = compute_field_distribution(group_df, field, config.min_coverage_for_field)
            row = {g: group_keys[i] for i, g in enumerate(group_cols)}
            row["field"] = field
            row["total_trades"] = dist["total_trades"]
            row["known_count"] = dist["known_count"]
            row["unknown_count"] = dist["unknown_count"]
            row["coverage_rate"] = dist["coverage_rate"]
            row["readiness_status"] = dist["readiness_status"]
            row["dominant_value"] = dist["dominant_value"]
            row["dominant_value_share"] = dist["dominant_value_share"]
            row["distribution_json"] = dist["distribution_json"]
            row["informational_only"] = True
            rows.append(row)

    return pd.DataFrame(rows)


def compute_field_readiness_overview(summary_df: pd.DataFrame,
                                     fields: List[str]) -> pd.DataFrame:
    """Aggregate field-level readiness across all groups."""
    rows = []
    for field in fields:
        sf = summary_df[summary_df["field"] == field]
        if len(sf) == 0:
            rows.append({"field": field, "coverage_rate": 0.0,
                         "readiness_status": "BLOCK", "reason": "No data"})
            continue
        avg_coverage = sf["coverage_rate"].mean()
        statuses = sf["readiness_status"].unique()
        if "BLOCK" in statuses:
            worst = "BLOCK"
        elif "WARN" in statuses:
            worst = "WARN"
        else:
            worst = "PASS"
        rows.append({
            "field": field,
            "coverage_rate": round(avg_coverage, 4),
            "readiness_status": worst,
            "reason": _field_readiness_reason(field, avg_coverage, worst),
        })
    return pd.DataFrame(rows)


def _field_readiness_reason(field: str, coverage: float, status: str) -> str:
    reasons = {
        "session": "Built-in UTC-hour rules, always available.",
        "structure_state": "Derived from regime field, always available.",
        "volatility_state": "From original trade log, always available.",
        "oi_state": "CoinGlass OI 1d × 365, 97.3% coverage.",
        "funding_state": "CoinGlass Funding 1d × 365, 97.5% coverage.",
        "etf_flow_state": "CoinGlass ETF daily, 100% coverage (BTC 2024+, ETH 2024-07+).",
    }
    if field in reasons:
        return reasons[field]
    if status == "BLOCK":
        return f"Cannot meet minimum coverage of 80%."
    return f"Coverage {coverage:.1%}."


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def build_context_report(summary_df: pd.DataFrame, field_overview: pd.DataFrame,
                         config: PartialContextConfig,
                         input_used: str,
                         excluded_reasons: dict) -> str:
    lines = []

    def h(lvl, text):
        lines.append(f"{'#' * lvl} {text}")

    def p(text=""):
        lines.append(text)

    # ── Header ──
    h(1, "Partial Context Report")
    p()
    p(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    p(f"**模式：** `{config.mode}`")
    p()
    p("> ⚠️ **INFORMATIONAL ONLY** — 本报告不改变 Enable Score / status / 评分逻辑。")
    p("> 本报告仅用于辅助人工复盘，不作为交易决策依据。")
    p()

    # ── Executive Summary ──
    h(2, "Executive Summary")
    p()
    p(f"- **输入文件：** `{input_used}`")
    p(f"- **输出目录：** `{config.output_dir}`")
    p(f"- **分组维度：** {', '.join(config.group_by)}")
    groups = summary_df[config.group_by].drop_duplicates()
    p(f"- **分组数：** {len(groups)}")
    p(f"- **Included fields：** {', '.join(config.fields)}")
    p(f"- **Excluded fields：** {', '.join(config.excluded_fields)}")
    p(f"- **Informational only：** {config.informational_only}")
    p()

    h(2, "Why Partial Context Only")
    p()
    p("- **Automatic Regime Classifier：** 仍 BLOCK（orderflow_state 86% unknown）")
    p("- **Full Market Opportunity Score：** 仍 BLOCK（依赖 orderflow + calendar）")
    p("- **orderflow_state：** Hobbyist taker 4h limit=365 → 仅 60 天覆盖")
    p("- **macro_state：** 32.8% fallback neutral，非真实 macro event coverage")
    p("- **当前只适合人工复盘上下文，不适合自动决策**")
    p()

    # ── Field Readiness ──
    h(2, "Field Readiness Overview")
    p()
    p("| Field | Coverage Rate | Readiness | Reason |")
    p("|-------|--------------|-----------|--------|")
    for _, row in field_overview.iterrows():
        p(f"| {row['field']} | {row['coverage_rate']:.1%} | **{row['readiness_status']}** | {row['reason']} |")
    p()

    # ── Strategy / Regime Context ──
    h(2, "Strategy / Regime Context Summary")
    p()
    group_cols = config.group_by
    gdf = summary_df.copy()

    for _, grp in groups.iterrows():
        group_label = " / ".join(str(grp[c]) for c in group_cols)
        mask = pd.Series(True, index=gdf.index)
        for c in group_cols:
            mask &= gdf[c] == grp[c]
        sf = gdf[mask]

        h(3, group_label)
        p()
        total = sf.iloc[0]["total_trades"] if len(sf) > 0 else 0
        p(f"- **总交易数：** {total}")
        p()

        # Dominant values table
        p("| Field | Dominant Value | Share | Coverage | Readiness |")
        p("|-------|---------------|-------|----------|-----------|")
        for _, r in sf.iterrows():
            status_mark = ""
            if r["readiness_status"] == "WARN":
                status_mark = " ⚠️"
            elif r["readiness_status"] == "BLOCK":
                status_mark = " ❌"
            dom = r["dominant_value"]
            p(f"| {r['field']} | **{dom}** | {r['dominant_value_share']:.1%} | {r['coverage_rate']:.1%} | **{r['readiness_status']}**{status_mark} |")

        # Distribution details
        for _, r in sf.iterrows():
            if r["distribution_json"] and r["distribution_json"] != "{}":
                try:
                    dist = json.loads(r["distribution_json"])
                    dist_items = sorted(dist.items(), key=lambda x: x[1], reverse=True)
                    dist_str = ", ".join(f"{k}: {v}" for k, v in dist_items[:5])
                    p(f"  - **{r['field']}** 分布: {dist_str}")
                except (json.JSONDecodeError, KeyError):
                    pass

        p()
        p("> ℹ️ 以上信息仅用于 context 理解，**不用于 Enable Score 计算**。")
        p()

    # ── Excluded Fields ──
    h(2, "Excluded Fields")
    p()
    p("以下字段在当前 partial_context_mode 中被排除：")
    p()
    p("| Field | Reason |")
    p("|-------|--------|")
    for field in config.excluded_fields:
        reason = excluded_reasons.get(field, "Excluded by configuration.")
        p(f"| {field} | {reason} |")
    p()

    # ── Usage Guidance ──
    h(2, "Usage Guidance")
    p()
    p("✅ **可以用于：**")
    p("- 人工复盘时理解 strategy/regime 的历史外部市场环境")
    p("- 辅助判断策略在不同环境下的行为分布")
    p("- 作为数据质量报告的补充")
    p()
    p("❌ **不可用于：**")
    p("- 自动开关策略（需 classifier）")
    p("- 调整 enable_score 或 status")
    p("- 作为 Market Opportunity Score 输入")
    p("- 替代人工对环境的判断")
    p()

    # ── Next Step ──
    h(2, "Next Step")
    p()
    p("**建议：P2-15 Data Quality Monitor 或 Context Report Review**")
    p()
    p("选择 A — Data Quality Monitor：在现有 label_quality + enrichment audit 基础上开发持续监控")
    p("选择 B — Context Report Review：基于本报告做人工 review 后决定下一步")
    p("选择 C — Degraded Market Opp Offline Experiment：OI+Funding+ETF 相关性探索（仅 offline）")
    p()

    # ── Generate metadata ──
    p()
    p("---")
    p()
    p(f"*Generated by Strategy Enable Score System v1.1 — P2-14 Partial Context Report*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(config_path: str, input_override: Optional[str] = None,
        quality_override: Optional[str] = None,
        output_dir_override: Optional[str] = None,
        dry_run: bool = False):
    """Main entry point for P2-14 context report generation."""
    full_config = load_config(config_path)
    pc = full_config.partial_context

    has_cli_override = bool(input_override or quality_override or output_dir_override)
    if not pc.enabled and not dry_run and not has_cli_override:
        logger.warning("partial_context.enabled is False. "
                       "Set partial_context.enabled=true in config.yaml, use --dry-run, or provide CLI overrides.")
        return

    input_path = input_override or pc.input_path
    quality_path = quality_override or pc.quality_summary_path
    output_dir = output_dir_override or pc.output_dir

    logger.info("=== Partial Context Report — %s ===", pc.mode)
    logger.info("Input: %s", input_path)
    logger.info("Quality summary: %s", quality_path)
    logger.info("Output dir: %s", output_dir)

    if dry_run:
        logger.info("=== DRY RUN — no files will be written ===")
        if not os.path.exists(input_path):
            logger.warning("Input file not found: %s", input_path)
        else:
            df = pd.read_csv(input_path)
            logger.info("Input trades: %d rows", len(df))
            logger.info("Group by: %s", pc.group_by)
            logger.info("Fields: %s", pc.fields)
            logger.info("Excluded: %s", pc.excluded_fields)
            logger.info("Outputs planned:")
            logger.info("  - %s/%s", output_dir, pc.summary_csv_name)
            logger.info("  - %s/%s", output_dir, pc.report_name)
        return

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    logger.info("Loaded %d trades", len(df))

    # Build summary
    summary_df = build_context_summary(df, pc)
    logger.info("Context summary: %d rows", len(summary_df))

    # Field readiness overview
    field_overview = compute_field_readiness_overview(summary_df, pc.fields)

    # Write summary CSV
    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, pc.summary_csv_name)
    summary_df.to_csv(summary_path, index=False)
    logger.info("Summary CSV: %s", summary_path)

    # Excluded field reasons (kept in memory, not in any config file)
    excluded_reasons = {
        "orderflow_state": "Readiness BLOCK — CoinGlass Hobbyist taker 4h 仅 60 天覆盖，86% unknown",
        "macro_state": "32.8% fallback neutral — 无 financial calendar (401 Hobbyist)，非真实 macro event coverage",
        "coinbase_premium_state": "No reliable data source configured",
    }

    # Build and write report
    report = build_context_report(summary_df, field_overview, pc,
                                   input_path, excluded_reasons)
    report_path = os.path.join(output_dir, pc.report_name)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Report: %s", report_path)

    logger.info("=== Done ===")


def main():
    parser = argparse.ArgumentParser(
        description="Strategy Enable Score System v1.1 — Partial Context Report (P2-14)"
    )
    parser.add_argument("--config", "-c", default="config.yaml",
                        help="Config file path")
    parser.add_argument("--input", "-i", default=None,
                        help="Override enriched trades CSV path")
    parser.add_argument("--quality-summary", "-q", default=None,
                        help="Override label quality summary CSV path")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="Override output directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, no writes")
    args = parser.parse_args()
    run(args.config, args.input, args.quality_summary,
        args.output_dir, args.dry_run)


if __name__ == "__main__":
    main()
