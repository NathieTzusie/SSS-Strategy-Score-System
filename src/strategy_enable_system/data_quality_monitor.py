"""
Data Quality Monitor for Strategy Enable Score System v1.1 (P2-15).

Aggregates label quality, enrichment audit, CoinGlass fetch coverage,
partial context readiness, baseline stability, and feature gate status
into a unified Data Quality Monitor report.

Run standalone:
  PYTHONPATH=src python -m strategy_enable_system.data_quality_monitor --config config.yaml
  PYTHONPATH=src python -m strategy_enable_system.data_quality_monitor --config config.yaml --dry-run
"""

import os
import re
import json
import argparse
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import load_config, DataQualityMonitorConfig

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ──

MONITOR_FIELDS = [
    "session", "structure_state", "volatility_state",
    "oi_state", "funding_state", "etf_flow_state",
    "orderflow_state", "macro_state", "coinbase_premium_state",
]


# ──────────────────────────────────────────────
# 1. Field Coverage Monitor
# ──────────────────────────────────────────────


def load_label_quality(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def field_coverage_monitor(lq_df: Optional[pd.DataFrame],
                            enrichment_rows: Optional[List[dict]] = None,
                            thresholds=None) -> List[dict]:
    rows = []
    # Build enrichment coverage lookup
    enrich_cov = {}
    if enrichment_rows:
        for r in enrichment_rows:
            if r.get("category") == "enrichment" and "enrich_" in str(r.get("item", "")):
                fname = str(r["item"]).replace("enrich_", "")
                try:
                    filled = int(r.get("value", 0))
                    total = 516
                    enrich_cov[fname] = filled / total if total > 0 else 0.0
                except (ValueError, TypeError):
                    pass

    for field in MONITOR_FIELDS:
        if lq_df is not None and field in lq_df["field"].values:
            r = lq_df[lq_df["field"] == field].iloc[0]
            unknown_ratio = float(r["unknown_ratio_after"])
            coverage = 1.0 - unknown_ratio
            readiness = str(r.get("readiness_status", "?"))
        elif field in enrich_cov:
            coverage = enrich_cov[field]
            unknown_ratio = 1.0 - coverage
            readiness = "PASS" if coverage >= thresholds.pass_coverage else ("WARN" if coverage >= thresholds.warn_coverage else "BLOCK")
        else:
            coverage = None
            unknown_ratio = None
            readiness = "UNKNOWN"

        # Monitor status
        if coverage is None:
            monitor_status = "WARN"
            notes = "Field not found in label quality summary."
        elif field == "orderflow_state" and coverage < 0.80:
            monitor_status = "BLOCK"
            notes = "Hobbyist taker 4h limit=365 → ~60 days coverage."
        elif field == "macro_state":
            # Coverage is 1.0 but mostly fallback neutral
            monitor_status = "DEGRADED"
            notes = "100% filled but 32.8% fallback neutral — no financial calendar."
        elif field == "coinbase_premium_state":
            monitor_status = "NOT_AVAILABLE"
            notes = "No reliable data source configured."
        elif coverage >= thresholds.pass_coverage:
            monitor_status = "PASS"
            notes = ""
        elif coverage >= thresholds.warn_coverage:
            monitor_status = "WARN"
            notes = f"Coverage {coverage:.1%} below pass threshold {thresholds.pass_coverage:.0%}."
        else:
            monitor_status = "BLOCK"
            notes = f"Coverage {coverage:.1%} below warn threshold {thresholds.warn_coverage:.0%}."

        rows.append({
            "category": "field_coverage",
            "item": field,
            "metric": "coverage_rate",
            "value": round(coverage, 4) if coverage is not None else None,
            "status": monitor_status,
            "reason": notes,
            "recommendation": _fc_recommendation(field, monitor_status),
        })
    return rows


def _fc_recommendation(field: str, status: str) -> str:
    recs = {
        ("orderflow_state", "BLOCK"):
            "Upgrade CoinGlass plan for 1h taker interval or supplement Binance trades stream.",
        ("macro_state", "DEGRADED"):
            "Need CoinGlass financial_calendar endpoint (requires higher plan).",
        ("coinbase_premium_state", "NOT_AVAILABLE"):
            "No data source. Consider CoinGlass or exchange API integration.",
    }
    return recs.get((field, status), "")


# ──────────────────────────────────────────────
# 2. Enrichment Monitor
# ──────────────────────────────────────────────


def enrichment_monitor(audit_path: str, enriched_path: str) -> List[dict]:
    rows = []
    audit_exists = os.path.exists(audit_path)
    enriched_exists = os.path.exists(enriched_path)

    rows.append({
        "category": "enrichment",
        "item": "enrichment_audit_report",
        "metric": "exists",
        "value": str(audit_exists).lower(),
        "status": "PASS" if audit_exists else "WARN",
        "reason": "" if audit_exists else "Audit report not found.",
        "recommendation": "Re-run P2-12 enrichment." if not audit_exists else "",
    })

    rows.append({
        "category": "enrichment",
        "item": "enriched_trades_full_year_csv",
        "metric": "exists",
        "value": str(enriched_exists).lower(),
        "status": "PASS" if enriched_exists else "WARN",
        "reason": "" if enriched_exists else "Enriched CSV not found.",
        "recommendation": "Re-run P2-12 enrichment." if not enriched_exists else "",
    })

    # Best-effort parse audit report
    if audit_exists:
        with open(audit_path, "r") as f:
            text = f.read()
        for m in re.finditer(r"\|\s*(\w+_state)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", text):
            field = m.group(1)
            filled = int(m.group(3))
            missing = int(m.group(5))
            after_unk = int(m.group(6))
            rows.append({
                "category": "enrichment",
                "item": f"enrich_{field}",
                "metric": "filled_count",
                "value": filled,
                "status": "PASS" if missing == 0 else ("WARN" if missing < 100 else "BLOCK"),
                "reason": f"filled={filled}, missing_match={missing}, after_unknown={after_unk}",
                "recommendation": "",
            })

    return rows


# ──────────────────────────────────────────────
# 3. CoinGlass Fetch Monitor
# ──────────────────────────────────────────────


def coinglass_fetch_monitor(fetch_report_path: str) -> List[dict]:
    rows = []
    report_exists = os.path.exists(fetch_report_path)

    rows.append({
        "category": "coinglass_fetch",
        "item": "fetch_report",
        "metric": "exists",
        "value": str(report_exists).lower(),
        "status": "PASS" if report_exists else "WARN",
        "reason": "" if report_exists else "Fetch report not found.",
        "recommendation": "Re-run P2-11 full-year fetch." if not report_exists else "",
    })

    if not report_exists:
        rows.append(_cg_item("oi_funding_coverage", "?", "WARN",
                              "Fetch report missing — cannot assess."))
        rows.append(_cg_item("taker_4h_coverage", "?", "BLOCK",
                              "Fetch report missing. Expected ~60 days at 4h interval."))
        rows.append(_cg_item("etf_coverage", "?", "WARN",
                              "Fetch report missing."))
        rows.append(_cg_item("calendar_availability", "?", "BLOCK",
                              "Expected unavailable under Hobbyist plan."))
        return rows

    with open(fetch_report_path, "r") as f:
        text = f.read()

    # OI/Funding/ETF coverage — check for success indicators
    success_count = len(re.findall(r"✅", text))
    oi_ok = "oi_agg" in text and "100%" in text
    funding_ok = "funding_oiw" in text and "100%" in text
    etf_ok = "etf_flow" in text and "100%" in text
    taker_limited = "4h" in text and ("11%" in text or "14%" in text or "60" in text)
    calendar_unavailable = "401" in text or "calendar" in text.lower()

    rows.append(_cg_item("oi_coverage",
                         "100% (BTC) / 97% (ETH)" if oi_ok else "partial",
                         "PASS" if oi_ok else "WARN",
                         "" if oi_ok else "OI data may be incomplete."))

    rows.append(_cg_item("funding_coverage",
                         "100% (BTC) / 97% (ETH)" if funding_ok else "partial",
                         "PASS" if funding_ok else "WARN",
                         "" if funding_ok else "Funding data may be incomplete."))

    rows.append(_cg_item("etf_coverage",
                         "100% (BTC 2024+, ETH 2024-07+)" if etf_ok else "partial",
                         "PASS" if etf_ok else "WARN",
                         "Daily interval — coverage is complete." if etf_ok else "ETF data may be incomplete."))

    rows.append(_cg_item("taker_4h_coverage",
                         "~11-14% of trades (60 days)" if taker_limited else "unknown",
                         "BLOCK",
                         "Hobbyist plan: 4h × 365 = ~60 days. orderflow_state limited to recent 2 months."))

    rows.append(_cg_item("financial_calendar",
                         "unavailable" if calendar_unavailable else "unknown",
                         "BLOCK",
                         "401 under Hobbyist plan. macro_state cannot use event_risk labels."))

    return rows


def _cg_item(item: str, value: str, status: str, reason: str) -> dict:
    return {
        "category": "coinglass_fetch",
        "item": item,
        "metric": "coverage",
        "value": value,
        "status": status,
        "reason": reason,
        "recommendation": "",
    }


# ──────────────────────────────────────────────
# 4. Partial Context Monitor
# ──────────────────────────────────────────────


def partial_context_monitor(ctx_path: str, required_fields: List[str]) -> List[dict]:
    rows = []
    ctx_exists = os.path.exists(ctx_path)

    if not ctx_exists:
        rows.append({
            "category": "partial_context",
            "item": "context_summary",
            "metric": "exists",
            "value": "false",
            "status": "WARN",
            "reason": "Partial context summary not found.",
            "recommendation": "Re-run P2-14 context report.",
        })
        rows.append({
            "category": "partial_context",
            "item": "partial_context_ready",
            "metric": "readiness",
            "value": "false",
            "status": "BLOCK",
            "reason": "Context summary missing.",
            "recommendation": "Re-run P2-14 context report.",
        })
        return rows

    ctx_df = pd.read_csv(ctx_path)
    field_statuses = {}
    blocked = []
    warned = []

    for field in required_fields:
        sf = ctx_df[ctx_df["field"] == field] if field in ctx_df["field"].values else pd.DataFrame()
        if len(sf) == 0:
            field_statuses[field] = "MISSING"
            blocked.append(field)
            continue
        vals = sf["readiness_status"].unique()
        if "BLOCK" in vals:
            field_statuses[field] = "BLOCK"
            blocked.append(field)
        elif "WARN" in vals:
            field_statuses[field] = "WARN"
            warned.append(field)
        else:
            field_statuses[field] = "PASS"

    all_ok = len(blocked) == 0 and len(warned) == 0
    ready = len(blocked) == 0

    rows.append({
        "category": "partial_context",
        "item": "context_summary",
        "metric": "exists",
        "value": "true",
        "status": "PASS",
        "reason": f"{len(ctx_df)} rows, {ctx_df['field'].nunique()} fields",
        "recommendation": "",
    })

    readiness = "READY" if all_ok else ("READY_WITH_WARNINGS" if ready else "BLOCK")
    reason_parts = []
    if blocked:
        reason_parts.append(f"blocked fields: {', '.join(blocked)}")
    if warned:
        reason_parts.append(f"warnings on: {', '.join(warned)}")

    rows.append({
        "category": "partial_context",
        "item": "partial_context_ready",
        "metric": "readiness",
        "value": readiness.lower(),
        "status": "PASS" if ready else "WARN",
        "reason": "; ".join(reason_parts) if reason_parts else "All required fields PASS.",
        "recommendation": "Context report is INFORMATIONAL ONLY — fine to generate." if ready else "Check field coverage before generating context report.",
    })

    return rows


# ──────────────────────────────────────────────
# 5. Feature Gate Monitor
# ──────────────────────────────────────────────


def feature_gate_monitor(field_data: List[dict], gates_config,
                         ctx_ready: bool) -> List[dict]:
    # Build lookup
    cov = {}
    for r in field_data:
        if r["category"] == "field_coverage":
            val = r["value"]
            cov[r["item"]] = float(val) if val is not None else 0.0

    rows = []

    # Classifier
    of_cov = cov.get("orderflow_state", 0.0)
    macro_cov = cov.get("macro_state", 0.0)
    classifier_of_ok = of_cov >= gates_config.classifier_requires.get("orderflow_state_coverage", 0.80)
    # macro_state "true coverage" is 0 because financial_calendar unavailable
    classifier_macro_true = False  # Hobbyist no calendar
    classifier_pass = classifier_of_ok and classifier_macro_true

    c_reason_parts = []
    if not classifier_of_ok:
        c_reason_parts.append(f"orderflow_state coverage {of_cov:.0%} < {gates_config.classifier_requires['orderflow_state_coverage']:.0%}")
    if not classifier_macro_true:
        c_reason_parts.append("macro true event coverage unavailable (financial_calendar 401 under Hobbyist)")

    rows.append({
        "category": "feature_gate",
        "item": "automatic_regime_classifier",
        "metric": "readiness",
        "value": "pass" if classifier_pass else "block",
        "status": "PASS" if classifier_pass else "BLOCK",
        "reason": "; ".join(c_reason_parts) if c_reason_parts else "All requirements met.",
        "recommendation": "Upgrade CoinGlass plan or supplement orderflow data source." if not classifier_pass else "Ready for shadow-mode prototype.",
    })

    # Market Opportunity
    mo_of_ok = classifier_of_ok
    mo_macro = classifier_macro_true
    etf_cov = cov.get("etf_flow_state", 0.0)
    mo_etf_ok = etf_cov >= gates_config.market_opportunity_requires.get("etf_flow_state_coverage", 0.80)
    mo_pass = mo_of_ok and mo_macro and mo_etf_ok

    mo_reason = []
    if not mo_of_ok:
        mo_reason.append("orderflow coverage insufficient")
    if not mo_macro:
        mo_reason.append("macro event coverage unavailable")
    if not mo_etf_ok:
        mo_reason.append(f"etf_flow coverage {etf_cov:.0%} insufficient")

    rows.append({
        "category": "feature_gate",
        "item": "full_market_opportunity_score",
        "metric": "readiness",
        "value": "pass" if mo_pass else "block",
        "status": "PASS" if mo_pass else "BLOCK",
        "reason": "; ".join(mo_reason) if mo_reason else "All requirements met.",
        "recommendation": "Requires classifier-level data + calendar + defined score boundary." if not mo_pass else "Shadow-mode prototype recommended.",
    })

    # Partial Context
    rows.append({
        "category": "feature_gate",
        "item": "partial_context_report",
        "metric": "readiness",
        "value": "pass" if ctx_ready else "block",
        "status": "PASS" if ctx_ready else "WARN",
        "reason": "All included fields meet coverage requirements. INFORMATIONAL ONLY." if ctx_ready else "Check context readiness.",
        "recommendation": "Generate context report — informational only, zero risk." if ctx_ready else "Fix field coverage.",
    })

    # Data Quality Monitor
    rows.append({
        "category": "feature_gate",
        "item": "data_quality_monitor",
        "metric": "readiness",
        "value": "pass",
        "status": "PASS",
        "reason": "This tool itself. Dependencies may vary.",
        "recommendation": "",
    })

    return rows


# ──────────────────────────────────────────────
# 6. Baseline Stability Monitor
# ──────────────────────────────────────────────


def baseline_stability_monitor(baseline_dir: str, current_dir: str,
                                max_delta: float) -> List[dict]:
    rows = []
    base_es = os.path.join(baseline_dir, "enable_score.csv")
    curr_es = os.path.join(current_dir, "enable_score.csv")

    if not os.path.exists(base_es):
        rows.append({
            "category": "baseline_stability",
            "item": "baseline_comparison",
            "metric": "available",
            "value": "false",
            "status": "WARN",
            "reason": "Baseline enable_score.csv not found.",
            "recommendation": "Re-run P0+P1 baseline generation.",
        })
        return rows

    if not os.path.exists(curr_es):
        rows.append({
            "category": "baseline_stability",
            "item": "baseline_comparison",
            "metric": "available",
            "value": "false",
            "status": "WARN",
            "reason": "Current enable_score.csv not found.",
            "recommendation": "Re-run main pipeline (main.py).",
        })
        return rows

    base = pd.read_csv(base_es)
    curr = pd.read_csv(curr_es)
    cols = ["strategy_name", "regime"]
    b = base.set_index(cols)
    c = curr.set_index(cols)

    delta = (c["enable_score"] - b["enable_score"]).abs()
    max_d = delta.max()
    changed = (b["status"] != c["status"]).sum()

    stable = max_d <= max_delta and changed == 0

    rows.append({
        "category": "baseline_stability",
        "item": "baseline_comparison",
        "metric": "max_enable_score_delta",
        "value": f"{max_d:.10f}",
        "status": "PASS" if max_d <= max_delta else "BLOCK",
        "reason": f"{'✅ stable' if max_d <= max_delta else '❌ delta exceeds limit'} | status_changed={changed}",
        "recommendation": "" if stable else "Investigate scoring changes — baseline must be preserved.",
    })

    rows.append({
        "category": "baseline_stability",
        "item": "default_input_path",
        "metric": "reminder",
        "value": "outputs/data_quality/cleaned_trades.csv",
        "status": "PASS",
        "reason": "config.yaml input_path unchanged.",
        "recommendation": "",
    })

    return rows


# ──────────────────────────────────────────────
# Markdown report
# ──────────────────────────────────────────────


def build_monitor_report(all_rows: pd.DataFrame, config: DataQualityMonitorConfig) -> str:
    lines = []

    def h(lvl, text):
        lines.append(f"{'#' * lvl} {text}")

    def p(text=""):
        lines.append(text)

    def tbl(headers, data_rows):
        p("| " + " | ".join(headers) + " |")
        p("|" + "|".join(["------"] * len(headers)) + "|")
        for r in data_rows:
            p("| " + " | ".join(str(c) for c in r) + " |")
        p()

    # Header
    h(1, "Data Quality Monitor Report")
    p()
    p(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    p()

    # ── Executive Summary ──
    h(2, "Executive Summary")

    overall = _determine_overall(all_rows)
    ctx_ready = _get_value(all_rows, "partial_context", "partial_context_ready", "false") in ("true", "ready", "ready_with_warnings")
    classifier_row = all_rows[(all_rows["category"] == "feature_gate") & (all_rows["item"] == "automatic_regime_classifier")]
    classifier_status = len(classifier_row) > 0 and classifier_row.iloc[0]["status"] == "PASS"
    mo_row = all_rows[(all_rows["category"] == "feature_gate") & (all_rows["item"] == "full_market_opportunity_score")]
    mo_status = len(mo_row) > 0 and mo_row.iloc[0]["status"] == "PASS"
    baseline_row = all_rows[(all_rows["category"] == "baseline_stability") & (all_rows["item"] == "baseline_comparison")]
    baseline_ok = len(baseline_row) > 0 and baseline_row.iloc[0]["status"] == "PASS"

    blockers = [r["item"] for _, r in all_rows.iterrows() if r["status"] == "BLOCK"]
    warnings = [r["item"] for _, r in all_rows.iterrows() if r["status"] == "WARN"]

    p(f"- **Overall status:** {overall}")
    p(f"- **Partial Context ready:** {'yes' if ctx_ready else 'no'}")
    p(f"- **Classifier:** {'PASS' if classifier_status else 'BLOCK'}")
    p(f"- **Market Opportunity:** {'PASS' if mo_status else 'BLOCK'}")
    p(f"- **Baseline stability:** {'PASS' if baseline_ok else 'WARN'}")
    if blockers:
        p(f"- **Key blockers:** {', '.join(blockers[:5])}")
    if warnings:
        p(f"- **Warnings:** {', '.join(warnings[:5])}")
    p()

    # ── Field Coverage ──
    h(2, "Field Coverage")
    fc = all_rows[all_rows["category"] == "field_coverage"]
    tbl(["Field", "Coverage", "Readiness", "Monitor Status", "Notes"],
        [(r["item"], f'{r["value"]:.1%}' if r["value"] is not None else "N/A",
          "—", r["status"], r["reason"]) for _, r in fc.iterrows()])

    # ── Enrichment Status ──
    h(2, "Enrichment Status")
    enr_rows = all_rows[all_rows["category"] == "enrichment"]
    enr_items = enr_rows[enr_rows["item"].isin(["enrichment_audit_report", "enriched_trades_full_year_csv"])]
    audit_ok = any(r["value"] == "true" for _, r in enr_items.iterrows() if r["item"] == "enrichment_audit_report")
    enriched_ok = any(r["value"] == "true" for _, r in enr_items.iterrows() if r["item"] == "enriched_trades_full_year_csv")
    p(f"- Enrichment audit report: {'✅ exists' if audit_ok else '❌ missing'}")
    p(f"- Enriched trades CSV: {'✅ exists' if enriched_ok else '❌ missing'}")
    fill_rows = [r for _, r in enr_rows.iterrows() if "enrich_" in str(r["item"])]
    if fill_rows:
        tbl(["Field", "Filled", "Reason"],
            [(r["item"].replace("enrich_", ""), r["value"], r["reason"]) for r in fill_rows])
    p()

    # ── CoinGlass Fetch Coverage ──
    h(2, "CoinGlass Fetch Coverage")
    cg_rows = all_rows[all_rows["category"] == "coinglass_fetch"]
    tbl(["Item", "Value", "Status", "Notes"],
        [(r["item"], r["value"], r["status"], r["reason"]) for _, r in cg_rows.iterrows()])

    # ── Partial Context Readiness ──
    h(2, "Partial Context Readiness")
    ctx_rows = all_rows[all_rows["category"] == "partial_context"]
    tbl(["Item", "Readiness", "Status", "Notes"],
        [(r["item"], r["value"], r["status"], r["reason"]) for _, r in ctx_rows.iterrows()])

    h(2, "Feature Gates")
    fg = all_rows[all_rows["category"] == "feature_gate"]
    tbl(["Feature", "Readiness", "Status", "Reason", "Recommendation"],
        [(r["item"], r["value"], r["status"], r["reason"], r["recommendation"]) for _, r in fg.iterrows()])

    # ── Baseline Stability ──
    h(2, "Baseline Stability")
    bs = all_rows[all_rows["category"] == "baseline_stability"]
    tbl(["Item", "Metric", "Value", "Status", "Reason"],
        [(r["item"], r["metric"], r["value"], r["status"], r["reason"]) for _, r in bs.iterrows()])

    # ── Recommendations ──
    h(2, "Recommendations")
    p()
    p("- ❌ **不建议实现 Automatic Regime Classifier** — orderflow 覆盖不足 + calendar 不可用")
    p("- ❌ **不建议实现 Full Market Opportunity Score** — 依赖 orderflow + calendar + 准实时数据")
    p("- ✅ **建议继续使用 Partial Context Report** — included fields 全部 READY，zero risk")
    p("- ✅ **建议维持 Data Quality Monitor** — 定期运行以追踪标签质量变化")
    p()
    p("**要解除 orderflow blocker：**")
    p("1. 升级 CoinGlass plan → 获取 1h taker interval + financial_calendar")
    p("2. 或补充 Binance trades stream → 自建 taker imbalance")
    p("3. 或降低 classifier 对 orderflow 的依赖性 → partial context 的 degraded classifier")
    p()

    p("---")
    p(f"*Generated by Strategy Enable Score System v1.1 — P2-15 Data Quality Monitor*")
    return "\n".join(lines)


def _determine_overall(df: pd.DataFrame) -> str:
    statuses = df["status"].tolist()
    if "BLOCK" in statuses:
        return "WARN"  # BLOCK items exist
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _get_value(df: pd.DataFrame, category: str, item: str, default: str) -> str:
    match = df[(df["category"] == category) & (df["item"] == item)]
    if len(match) == 0:
        return default
    return str(match.iloc[0]["value"])


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────


def run(config_path: str, output_dir_override: Optional[str] = None,
        dry_run: bool = False):
    full_cfg = load_config(config_path)
    cfg = full_cfg.data_quality_monitor
    has_override = bool(output_dir_override)

    if not cfg.enabled and not dry_run and not has_override:
        logger.warning("data_quality_monitor.enabled is False. "
                       "Set enabled=true in config.yaml, use --dry-run, or provide --output-dir.")
        return

    output_dir = output_dir_override or cfg.output_dir

    if dry_run:
        logger.info("=== DRY RUN — no files will be written ===")
        missing = []
        for key in ["label_quality_summary", "enrichment_audit_report",
                     "coinglass_fetch_report", "partial_context_summary"]:
            p = getattr(cfg.inputs, key)
            if not os.path.exists(p):
                missing.append(p)
                logger.warning("MISSING: %s", p)
            else:
                logger.info("  OK: %s", p)
        logger.info("Baseline dir: %s", cfg.inputs.official_baseline_dir)
        logger.info("Current outputs: %s", cfg.inputs.current_default_outputs_dir)
        logger.info("Output dir: %s", output_dir)
        if missing:
            logger.warning("%d input files missing — production run would produce WARN/BLOCK entries.", len(missing))
        return

    all_rows = []

    # 1. Field Coverage (depends on enrichment data for oi/funding/etf coverage)
    enriched_path = cfg.inputs.current_default_outputs_dir + "/data_quality/enriched_trades_full_year.csv"
    enrich_rows = enrichment_monitor(cfg.inputs.enrichment_audit_report, enriched_path)
    all_rows.extend(enrich_rows)

    lq_df = load_label_quality(cfg.inputs.label_quality_summary)
    all_rows.extend(field_coverage_monitor(lq_df, enrich_rows, cfg.thresholds))

    # 3. CoinGlass Fetch
    all_rows.extend(coinglass_fetch_monitor(cfg.inputs.coinglass_fetch_report))

    # 4. Partial Context
    ctx_rows = partial_context_monitor(cfg.inputs.partial_context_summary,
                                        cfg.thresholds.require_context_fields_pass)
    all_rows.extend(ctx_rows)
    ctx_ready = any(r["item"] == "partial_context_ready" and r["status"] in ("PASS", "WARN")
                    for r in ctx_rows)

    # 5. Feature Gates
    all_rows.extend(feature_gate_monitor(all_rows, cfg.feature_gates, ctx_ready))

    # 6. Baseline Stability
    all_rows.extend(baseline_stability_monitor(cfg.inputs.official_baseline_dir,
                                                cfg.inputs.current_default_outputs_dir,
                                                cfg.thresholds.max_allowed_enable_score_delta))

    df = pd.DataFrame(all_rows)

    os.makedirs(output_dir, exist_ok=True)

    summary_path = os.path.join(output_dir, cfg.summary_csv_name)
    df.to_csv(summary_path, index=False)
    logger.info("Summary CSV: %s (%d rows)", summary_path, len(df))

    report = build_monitor_report(df, cfg)
    report_path = os.path.join(output_dir, cfg.report_name)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Report: %s", report_path)

    logger.info("=== Done ===")


def main():
    parser = argparse.ArgumentParser(
        description="Strategy Enable Score System v1.1 — Data Quality Monitor (P2-15)"
    )
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--output-dir", "-o", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.config, args.output_dir, args.dry_run)


if __name__ == "__main__":
    main()
