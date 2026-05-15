"""
Recommendations Module for Strategy Enable Score System v1.1.
Generates data-driven improvement recommendations from performance data.

Analyzes four grouping dimensions:
  1. strategy
  2. strategy × regime
  3. strategy × direction
  4. strategy × regime × direction

Produces structured recommendations (CSV + Markdown) with five action types:
  disable — performance clearly negative
  downweight — performance weak
  optimize — entries or exits need tuning
  monitor — insufficient data
  info — informational only
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd

from .utils import to_csv_utf8sig

# ─────────────────────────────────────────────────────────────────────────────
# Type aliases
# ─────────────────────────────────────────────────────────────────────────────

RecommendationScope = Literal[
    "strategy",
    "strategy_regime",
    "strategy_direction",
    "strategy_regime_direction",
]

RecommendationAction = Literal[
    "disable",
    "downweight",
    "optimize",
    "monitor",
    "info",
]

RecommendationSeverity = Literal[
    "critical",
    "warning",
    "info",
]

# Metrics columns used for evaluation
METRIC_COLUMNS = [
    "trade_count",
    "win_rate",
    "profit_factor",
    "avg_R",
    "total_R",
    "max_drawdown_R",
    "payoff_ratio",
]


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecommendationsConfig:
    """Thresholds and knobs for recommendation generation."""

    enabled: bool = True

    min_strategy_trade_count: int = 30
    min_group_trade_count: int = 15

    # Profit factor thresholds
    poor_profit_factor: float = 1.0
    weak_profit_factor: float = 1.2

    # Win rate thresholds
    poor_win_rate: float = 0.45
    weak_win_rate: float = 0.50

    # Drawdown
    high_drawdown_R: float = 5.0

    # Payoff ratio
    low_payoff_ratio: float = 0.8
    high_payoff_ratio: float = 1.5

    # Average R
    poor_avg_R: float = 0.0

    # Loss concentration
    high_loss_concentration_R: float = 0.5

    # Output limits
    max_recommendations: int = 50


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation record
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    """A single data-driven recommendation."""

    scope: RecommendationScope
    action: RecommendationAction
    severity: RecommendationSeverity

    strategy_name: str
    regime: Optional[str] = None
    direction: Optional[str] = None

    trade_count: int = 0
    profit_factor: Optional[float] = None
    win_rate: Optional[float] = None
    avg_R: Optional[float] = None
    max_drawdown_R: Optional[float] = None
    payoff_ratio: Optional[float] = None
    enable_score: Optional[float] = None
    status: Optional[str] = None

    reason: str = ""
    recommendation: str = ""
    priority_score: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecommendationResult:
    """Container for the full recommendation output."""

    recommendations: List[Recommendation] = field(default_factory=list)
    markdown: str = ""

    def dataframe(self) -> pd.DataFrame:
        return recommendations_to_dataframe(self.recommendations)

    def write_csv(self, path: str) -> None:
        df = self.dataframe()
        to_csv_utf8sig(df, path)

    def write_markdown(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.markdown)


# ─────────────────────────────────────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def generate_recommendations(
    performance_matrix: pd.DataFrame,
    enable_scores: pd.DataFrame,
    trades: pd.DataFrame,
    config: Optional[RecommendationsConfig] = None,
) -> RecommendationResult:
    """Generate data-driven recommendations from strategy performance data.

    Args:
        performance_matrix: strategy × regime performance DataFrame.
        enable_scores: enable score results DataFrame.
        trades: per-trade DataFrame with strategy_name, regime, direction, pnl_R.
        config: thresholds config. Uses defaults when None.

    Returns:
        RecommendationResult with .recommendations list and .markdown rendering.
    """
    cfg = config or RecommendationsConfig()
    if not cfg.enabled:
        return RecommendationResult(recommendations=[], markdown="")

    recs: List[Recommendation] = []

    # ── 1. Strategy-level ──
    sym_groups = _aggregate_groups(trades, ["strategy_name"], cfg)
    for _, row in sym_groups.iterrows():
        rec = _evaluate_group(row, cfg, "strategy", enable_scores, trades)
        if rec:
            recs.append(rec)

    # ── 2. Strategy × regime ──
    sr_groups = _aggregate_groups(trades, ["strategy_name", "regime"], cfg)
    for _, row in sr_groups.iterrows():
        rec = _evaluate_group(row, cfg, "strategy_regime", enable_scores, trades)
        if rec:
            recs.append(rec)

    # ── 3. Strategy × direction ──
    sd_groups = _aggregate_groups(trades, ["strategy_name", "direction"], cfg)
    for _, row in sd_groups.iterrows():
        rec = _evaluate_group(row, cfg, "strategy_direction", enable_scores, trades)
        if rec:
            recs.append(rec)

    # ── 4. Strategy × regime × direction ──
    srd_groups = _aggregate_groups(trades, ["strategy_name", "regime", "direction"], cfg)
    for _, row in srd_groups.iterrows():
        rec = _evaluate_group(row, cfg, "strategy_regime_direction", enable_scores, trades)
        if rec:
            recs.append(rec)

    recs = _rank_recommendations(recs, cfg.max_recommendations)
    markdown = _render_recommendations_markdown(recs)

    return RecommendationResult(recommendations=recs, markdown=markdown)


# ─────────────────────────────────────────────────────────────────────────────
# Group aggregation
# ─────────────────────────────────────────────────────────────────────────────

def _aggregate_groups(
    trades: pd.DataFrame,
    group_cols: List[str],
    config: RecommendationsConfig,
) -> pd.DataFrame:
    """Aggregate trade-level metrics by group columns.

    Returns a DataFrame with one row per group and computed metrics.
    """
    if trades.empty:
        return pd.DataFrame(columns=group_cols + METRIC_COLUMNS)

    def _agg(group: pd.DataFrame) -> pd.Series:
        n = len(group)
        wins = group[group["pnl_R"] > 0]
        losses = group[group["pnl_R"] <= 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / n if n > 0 else 0.0

        total_wins = wins["pnl_R"].sum() if win_count > 0 else 0.0
        total_losses = abs(losses["pnl_R"].sum()) if loss_count > 0 else 0.0

        avg_win = total_wins / win_count if win_count > 0 else 0.0
        avg_loss = total_losses / loss_count if loss_count > 0 else 0.0

        payoff = avg_win / avg_loss if avg_loss > 0 else (avg_win if avg_win > 0 else 0.0)
        profit_factor = total_wins / total_losses if total_losses > 0 else (total_wins if total_wins > 0 else 0.0)

        total_r = group["pnl_R"].sum()
        avg_r = total_r / n if n > 0 else 0.0

        # max drawdown via cumulative sum
        equity = group["pnl_R"].cumsum()
        running_max = equity.cummax()
        drawdowns = equity - running_max
        max_dd = abs(float(drawdowns.min())) if len(drawdowns) > 0 else 0.0

        return pd.Series({
            "trade_count": n,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_R": avg_r,
            "total_R": total_r,
            "max_drawdown_R": max_dd,
            "payoff_ratio": payoff,
        })

    grouped = trades.groupby(group_cols, dropna=False).apply(_agg).reset_index()
    return grouped


# ─────────────────────────────────────────────────────────────────────────────
# Rule engine
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_group(
    row: pd.Series,
    config: RecommendationsConfig,
    scope: RecommendationScope,
    enable_scores: pd.DataFrame,
    trades: pd.DataFrame,
) -> Optional[Recommendation]:
    """Evaluate one group row and return a Recommendation if any rule triggers."""
    n = int(row.get("trade_count", 0))
    pf = float(row.get("profit_factor", 0) or 0)
    wr = float(row.get("win_rate", 0) or 0)
    dd = float(row.get("max_drawdown_R", 0) or 0)
    payoff = float(row.get("payoff_ratio", 0) or 0)
    avg_r = float(row.get("avg_R", 0) or 0)

    strategy_name = str(row.get("strategy_name", "unknown"))
    regime = str(row.get("regime", "")) if "regime" in row.index and pd.notna(row.get("regime")) else None
    direction = str(row.get("direction", "")) if "direction" in row.index and pd.notna(row.get("direction")) else None

    # ── Fetch enable_score/status if available ──
    es_val: Optional[float] = None
    status_val: Optional[str] = None
    review_required: bool = False

    if not enable_scores.empty and regime is not None:
        match = enable_scores[
            (enable_scores["strategy_name"] == strategy_name)
            & (enable_scores["regime"] == regime)
        ]
        if len(match) > 0:
            es_val = float(match.iloc[0].get("enable_score", 0) or 0)
            status_val = str(match.iloc[0].get("status", "") or "")
            review_required = bool(match.iloc[0].get("review_required", False))

    # Insufficient data → monitor (skip if already has a stronger signal)
    if n < config.min_group_trade_count and es_val is None:
        return None  # don't generate recommendations for noise

    # ── Build description helpers ──
    def _scope_label() -> str:
        parts = [strategy_name]
        if regime:
            parts.append(regime)
        if direction:
            parts.append(direction)
        return " @ ".join(parts)

    label = _scope_label()
    evidence: Dict[str, Any] = {
        "trade_count": n,
        "profit_factor": round(pf, 3),
        "win_rate": round(wr, 3),
        "max_drawdown_R": round(dd, 2),
        "payoff_ratio": round(payoff, 3),
        "avg_R": round(avg_r, 3),
    }

    # ── Priority score base ──
    priority = 0.0

    # ═══════════════════════════════════════════════════════════
    # Rule 1: Disable — PF < 1.0 + DD high + sufficient data
    # ═══════════════════════════════════════════════════════════
    if pf < config.poor_profit_factor and n >= config.min_group_trade_count:
        action: RecommendationAction = "disable"
        severity: RecommendationSeverity = "critical"
        reason = f"PF {pf:.2f} < 1.0 (negative expectancy)"
        rec_text = f"Disable **{label}**: PF={pf:.2f}, DD={dd:.1f}R, {n} trades."

        priority += 100
        priority += max(0.0, 1.2 - pf) * 30
        priority += max(0.0, dd - config.high_drawdown_R) * 2
        priority += min(n, 100) / 10

        if status_val and "禁用" in str(status_val):
            priority += 25
        if review_required:
            priority += 15

        return Recommendation(
            scope=scope,
            action=action,
            severity=severity,
            strategy_name=strategy_name,
            regime=regime,
            direction=direction,
            trade_count=n,
            profit_factor=pf,
            win_rate=wr,
            avg_R=avg_r,
            max_drawdown_R=dd,
            payoff_ratio=payoff,
            enable_score=es_val,
            status=status_val,
            reason=reason,
            recommendation=rec_text,
            priority_score=priority,
            evidence=evidence,
        )

    # ═══════════════════════════════════════════════════════════
    # Rule 2: Downweight — PF 1.0~1.2 + enough data
    # ═══════════════════════════════════════════════════════════
    if config.poor_profit_factor <= pf < config.weak_profit_factor and n >= config.min_group_trade_count:
        action = "downweight"
        severity = "warning"
        reason = f"PF {pf:.2f} < {config.weak_profit_factor} (weak edge)"
        rec_text = f"Downweight **{label}**: PF={pf:.2f} is weak despite {n} trades."

        priority += 60
        priority += max(0.0, config.weak_profit_factor - pf) * 30
        priority += max(0.0, dd - config.high_drawdown_R) * 2
        priority += min(n, 100) / 20

        if status_val and "禁用" in str(status_val):
            priority += 25
        if review_required:
            priority += 15

        return Recommendation(
            scope=scope,
            action=action,
            severity=severity,
            strategy_name=strategy_name,
            regime=regime,
            direction=direction,
            trade_count=n,
            profit_factor=pf,
            win_rate=wr,
            avg_R=avg_r,
            max_drawdown_R=dd,
            payoff_ratio=payoff,
            enable_score=es_val,
            status=status_val,
            reason=reason,
            recommendation=rec_text,
            priority_score=priority,
            evidence=evidence,
        )

    # ═══════════════════════════════════════════════════════════
    # Rule 3: Optimize entries — low WR but payoff OK
    # ═══════════════════════════════════════════════════════════
    if wr < config.poor_win_rate and payoff >= config.low_payoff_ratio and n >= config.min_group_trade_count:
        action = "optimize"
        severity = "warning"
        reason = f"WR {wr:.1%} < {config.poor_win_rate:.0%} but payoff {payoff:.2f} ≥ {config.low_payoff_ratio}"
        rec_text = f"Optimize entries/filters for **{label}**: win rate {wr:.1%} is low, but payoff {payoff:.2f} is acceptable."

        priority += 30
        priority += (config.poor_win_rate - wr) * 100
        priority += min(n, 100) / 30

        if review_required:
            priority += 15

        return Recommendation(
            scope=scope,
            action=action,
            severity=severity,
            strategy_name=strategy_name,
            regime=regime,
            direction=direction,
            trade_count=n,
            profit_factor=pf,
            win_rate=wr,
            avg_R=avg_r,
            max_drawdown_R=dd,
            payoff_ratio=payoff,
            enable_score=es_val,
            status=status_val,
            reason=reason,
            recommendation=rec_text,
            priority_score=priority,
            evidence=evidence,
        )

    # ═══════════════════════════════════════════════════════════
    # Rule 4: Optimize exits — OK WR but payoff weak
    # ═══════════════════════════════════════════════════════════
    if wr >= config.weak_win_rate and payoff < config.low_payoff_ratio and n >= config.min_group_trade_count:
        action = "optimize"
        severity = "warning"
        reason = f"WR {wr:.1%} ≥ {config.weak_win_rate:.0%} but payoff {payoff:.2f} < {config.low_payoff_ratio}"
        rec_text = f"Optimize exits/stops for **{label}**: win rate {wr:.1%} is ok but payoff {payoff:.2f} is too low."

        priority += 30
        priority += (config.low_payoff_ratio - payoff) * 80
        priority += min(n, 100) / 30

        if review_required:
            priority += 15

        return Recommendation(
            scope=scope,
            action=action,
            severity=severity,
            strategy_name=strategy_name,
            regime=regime,
            direction=direction,
            trade_count=n,
            profit_factor=pf,
            win_rate=wr,
            avg_R=avg_r,
            max_drawdown_R=dd,
            payoff_ratio=payoff,
            enable_score=es_val,
            status=status_val,
            reason=reason,
            recommendation=rec_text,
            priority_score=priority,
            evidence=evidence,
        )

    # ═══════════════════════════════════════════════════════════
    # Rule 5: Monitor — insufficient data but ES shows risk
    # ═══════════════════════════════════════════════════════════
    if n < config.min_group_trade_count and (es_val is not None and (es_val < 50 or review_required)):
        action = "monitor"
        severity = "info"
        reason = f"Only {n} trades (< {config.min_group_trade_count}), but enable score {es_val:.0f} flagged."
        rec_text = f"Monitor **{label}**: insufficient data ({n} trades) but enable score {es_val:.0f} suggests risk."

        priority += 5
        if review_required:
            priority += 10

        return Recommendation(
            scope=scope,
            action=action,
            severity=severity,
            strategy_name=strategy_name,
            regime=regime,
            direction=direction,
            trade_count=n,
            profit_factor=pf,
            win_rate=wr,
            avg_R=avg_r,
            max_drawdown_R=dd,
            payoff_ratio=payoff,
            enable_score=es_val,
            status=status_val,
            reason=reason,
            recommendation=rec_text,
            priority_score=priority,
            evidence=evidence,
        )

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Ranking
# ─────────────────────────────────────────────────────────────────────────────

def _rank_recommendations(
    recommendations: List[Recommendation],
    max_items: int,
) -> List[Recommendation]:
    """Sort by priority_score descending, keep top max_items."""
    return sorted(recommendations, key=lambda r: r.priority_score, reverse=True)[:max_items]


# ─────────────────────────────────────────────────────────────────────────────
# DataFrame conversion
# ─────────────────────────────────────────────────────────────────────────────

def recommendations_to_dataframe(recommendations: List[Recommendation]) -> pd.DataFrame:
    """Convert recommendation list to a DataFrame for CSV output."""
    if not recommendations:
        return pd.DataFrame()

    rows = []
    for r in recommendations:
        rows.append({
            "scope": r.scope,
            "action": r.action,
            "severity": r.severity,
            "strategy_name": r.strategy_name,
            "regime": r.regime or "",
            "direction": r.direction or "",
            "trade_count": r.trade_count,
            "profit_factor": round(r.profit_factor, 4) if r.profit_factor is not None else "",
            "win_rate": round(r.win_rate, 4) if r.win_rate is not None else "",
            "avg_R": round(r.avg_R, 4) if r.avg_R is not None else "",
            "max_drawdown_R": round(r.max_drawdown_R, 4) if r.max_drawdown_R is not None else "",
            "payoff_ratio": round(r.payoff_ratio, 4) if r.payoff_ratio is not None else "",
            "enable_score": round(r.enable_score, 1) if r.enable_score is not None else "",
            "status": r.status or "",
            "priority_score": round(r.priority_score, 2),
            "reason": r.reason,
            "recommendation": r.recommendation,
        })

    df = pd.DataFrame(rows)
    # Sort by priority_score descending
    df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Markdown rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_recommendations_markdown(recommendations: List[Recommendation]) -> str:
    """Render recommendations as Markdown.

    Full version for recommendations.md.
    """
    if not recommendations:
        return "_No recommendations generated._"

    lines: List[str] = []
    lines.append("# Strategy Improvement Recommendations")
    lines.append("")
    lines.append("*Data-driven recommendations based on performance metrics, ")
    lines.append("enable scores, and trade-level analysis.*")
    lines.append("")

    # Group by severity
    by_severity: Dict[str, List[Recommendation]] = {"critical": [], "warning": [], "info": []}
    for r in recommendations:
        by_severity.setdefault(r.severity, []).append(r)

    severity_labels = {
        "critical": ("## 🔴 Critical", "These groups show clear negative performance and should be disabled or urgently reviewed."),
        "warning": ("## 🟡 Warning", "These groups show weak or sub-optimal performance that may need adjustment."),
        "info": ("## 🔵 Info", "Low-confidence or monitoring recommendations."),
    }

    for sev in ["critical", "warning", "info"]:
        items = by_severity.get(sev, [])
        if not items:
            continue

        heading, desc = severity_labels[sev]
        lines.append(heading)
        lines.append("")
        lines.append(desc)
        lines.append("")

        # Action labels
        action_map = {
            "disable": "⛔ Disable",
            "downweight": "⬇️ Downweight",
            "optimize": "🔧 Optimize",
            "monitor": "👀 Monitor",
            "info": "ℹ️ Info",
        }

        for i, r in enumerate(items, 1):
            lines.append(f"### {i}. {action_map.get(r.action, r.action)} — {r.strategy_name}")
            if r.regime or r.direction:
                scope_parts = []
                if r.regime:
                    scope_parts.append(f"regime=`{r.regime}`")
                if r.direction:
                    scope_parts.append(f"direction=`{r.direction}`")
                lines.append(f"**Scope:** {' × '.join(scope_parts)}")
            lines.append("")
            lines.append(f"**Recommendation:** {r.recommendation}")
            lines.append("")
            lines.append(f"**Reason:** {r.reason}")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Trades | {r.trade_count} |")
            if r.profit_factor is not None:
                lines.append(f"| Profit Factor | {r.profit_factor:.3f} |")
            if r.win_rate is not None:
                lines.append(f"| Win Rate | {r.win_rate:.1%} |")
            if r.payoff_ratio is not None:
                lines.append(f"| Payoff Ratio | {r.payoff_ratio:.3f} |")
            if r.max_drawdown_R is not None:
                lines.append(f"| Max DD (R) | {r.max_drawdown_R:.2f} |")
            if r.enable_score is not None:
                lines.append(f"| Enable Score | {r.enable_score:.0f} |")
            if r.status:
                lines.append(f"| Status | {r.status} |")
            lines.append("")

    lines.append("---")
    lines.append("*Generated by Strategy Enable Score System v1.1 — Recommendations Module*")
    return "\n".join(lines)


def render_recommendations_summary(recommendations: List[Recommendation]) -> str:
    """Render a short summary section for inclusion in summary_report.md.

    Only includes top 5 highest-priority recommendations.
    """
    if not recommendations:
        return ""

    lines: List[str] = []
    lines.append("## Data-Driven Improvement Recommendations")
    lines.append("")

    top = recommendations[:5]
    action_map = {
        "disable": "Disable",
        "downweight": "Downweight",
        "optimize": "Optimize",
        "monitor": "Monitor",
        "info": "Note",
    }

    for i, r in enumerate(top, 1):
        action_label = action_map.get(r.action, r.action)
        scope_parts = [r.strategy_name]
        if r.regime:
            scope_parts.append(r.regime)
        if r.direction:
            scope_parts.append(r.direction)
        label = " @ ".join(scope_parts)

        pf_str = f"PF={r.profit_factor:.2f}" if r.profit_factor is not None else ""
        dd_str = f"DD={r.max_drawdown_R:.1f}R" if r.max_drawdown_R is not None else ""
        wr_str = f"WR={r.win_rate:.1%}" if r.win_rate is not None else ""
        evidence_parts = [p for p in [pf_str, dd_str, wr_str, f"{r.trade_count}t"] if p]
        evidence_line = ", ".join(evidence_parts)

        lines.append(f"{i}. **{action_label}** `{label}` — {evidence_line}")
        lines.append(f"   > {r.recommendation}")

    lines.append("")
    lines.append(f"*{len(recommendations)} total recommendations generated. ")
    lines.append("See `recommendations.md` and `recommendations.csv` for the full list.*")
    return "\n".join(lines)
