"""
Scoring Module for Strategy Enable Score System v1.1.
Computes Strategy Enable Score, sub-scores, penalties, and explanation fields.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

from .config import SSSConfig
from .utils import clamp, safe_divide


def compute_enable_scores(
    performance_matrix: pd.DataFrame,
    monte_carlo_results: pd.DataFrame,
    config: SSSConfig,
) -> pd.DataFrame:
    """Compute Strategy Enable Score for each (strategy_name, regime) combination.
    
    Args:
        performance_matrix: Regime performance matrix.
        monte_carlo_results: Monte Carlo simulation results.
        config: SSSConfig object.
    
    Returns:
        pd.DataFrame: Enable score results with explanation fields.
    """
    # Merge performance and MC results
    mc = monte_carlo_results.copy()
    merged = performance_matrix.merge(
        mc, on=["strategy_name", "regime"], how="left", suffixes=("", "_mc")
    )
    
    results = []
    for _, row in merged.iterrows():
        result = _compute_single_score(row, config)
        results.append(result)
    
    df = pd.DataFrame(results)
    return df


def _compute_single_score(row: pd.Series, config: SSSConfig) -> Dict[str, Any]:
    """Compute enable score for a single strategy-regime combination."""
    
    # --- Sub-scores ---
    regime_edge = _compute_regime_edge_score(row, config)
    recent_health = _compute_recent_health_score(row, config)
    mc_stability = _compute_monte_carlo_stability_score(row, config)
    risk_control = _compute_risk_control_score(row, config)
    
    # --- Base Enable Score ---
    sw = config.score_weights
    base_score = (
        regime_edge * sw.regime_edge
        + recent_health * sw.recent_health
        + mc_stability * sw.monte_carlo_stability
        + risk_control * sw.risk_control
    )
    
    # --- Multipliers / Penalties ---
    sample_mult = _compute_sample_confidence_multiplier(row, config)
    recent_loss_penalty = _compute_recent_loss_penalty(row)
    mc_tail_penalty = _compute_mc_tail_risk_penalty(row)
    edge_penalty = _compute_edge_concentration_penalty(row, config)
    
    # --- Final Enable Score ---
    enable_score = base_score * sample_mult * recent_loss_penalty * mc_tail_penalty * edge_penalty
    enable_score = clamp(enable_score, 0.0, 100.0)
    
    # --- Market Opportunity (placeholder) ---
    market_opp_score = config.market_opportunity.default_score
    final_activation = enable_score * market_opp_score
    
    # --- Status ---
    status = _determine_status(enable_score, config)
    
    # --- Drivers ---
    score_drivers = _compute_score_drivers(regime_edge, recent_health, mc_stability, risk_control)
    penalty_drivers = _compute_penalty_drivers(sample_mult, recent_loss_penalty, mc_tail_penalty, edge_penalty, row)
    primary_reason = _determine_primary_reason(enable_score, base_score, penalty_drivers, row, config)
    risk_notes = _compute_risk_notes(row, penalty_drivers, config)
    review_required = _compute_review_required(row, penalty_drivers, config)
    
    return {
        "strategy_name": row["strategy_name"],
        "regime": row["regime"],
        "enable_score": round(enable_score, 2),
        "market_opportunity_score": market_opp_score,
        "final_activation_score": round(final_activation, 2),
        "status": status,
        
        "regime_edge_score": round(regime_edge, 2),
        "recent_health_score": round(recent_health, 2),
        "monte_carlo_stability_score": round(mc_stability, 2),
        "risk_control_score": round(risk_control, 2),
        
        "sample_confidence_multiplier": round(sample_mult, 4),
        "recent_loss_penalty": round(recent_loss_penalty, 4),
        "mc_tail_risk_penalty": round(mc_tail_penalty, 4),
        "edge_concentration_penalty": round(edge_penalty, 4),
        
        "score_drivers": ";".join(score_drivers) if score_drivers else "",
        "penalty_drivers": ";".join(penalty_drivers) if penalty_drivers else "",
        "primary_reason": primary_reason,
        "risk_notes": risk_notes,
        "review_required": review_required,
        "low_sample_warning": row.get("low_sample_warning", False),
        "edge_concentration_warning": row.get("edge_concentration_warning", False),
    }


# ============================================================
# Sub-score functions
# ============================================================

def _compute_regime_edge_score(row: pd.Series, config: SSSConfig) -> float:
    """Compute Regime Edge Score (weight: 0.40)."""
    tc = _trade_count_score(row.get("trade_count", 0), config.min_trades)
    wr = _win_rate_score(row.get("win_rate", 0))
    pf = _profit_factor_score(row.get("profit_factor", 0))
    ex = _expectancy_score(row.get("expectancy_R", 0))
    dd = _drawdown_score(row.get("max_drawdown_R", 0))
    
    return tc * 0.20 + wr * 0.20 + pf * 0.25 + ex * 0.25 + dd * 0.10


def _compute_recent_health_score(row: pd.Series, config: SSSConfig) -> float:
    """Compute Recent Health Score (weight: 0.15).
    
    Uses avg_R, win_rate, drawdown from recent window embedded in the row.
    For v1, we use overall metrics as proxy if recent data is unavailable.
    """
    # v1: use overall metrics as proxy for "recent" since we don't split
    # the data into recent/all subsets in the metrics module yet.
    # Recent health uses the same metrics but is interpreted as "recent context".
    recent_avg_r = _expectancy_score(row.get("avg_R", 0))
    recent_wr = _win_rate_score(row.get("win_rate", 0))
    recent_dd = _drawdown_score(row.get("max_drawdown_R", 0))
    recent_ls = _losing_streak_score(row.get("current_losing_streak", 0))
    
    return recent_avg_r * 0.35 + recent_wr * 0.25 + recent_dd * 0.25 + recent_ls * 0.15


def _compute_monte_carlo_stability_score(row: pd.Series, config: SSSConfig) -> float:
    """Compute Monte Carlo Stability Score (weight: 0.25)."""
    neg_prob = row.get("probability_of_negative_total_R", 0.5)
    p95_dd = row.get("p95_max_drawdown_R", -10)
    p95_ls = row.get("p95_longest_losing_streak", 8)
    p5_total = row.get("p5_total_R", -5)
    
    neg_score = (1.0 - neg_prob) * 100  # 0% negative → 100, 100% negative → 0
    p95_dd_score = _drawdown_score(p95_dd)
    p95_ls_score = _losing_streak_score(p95_ls)
    p5_total_score = clamp((p5_total + 10) / 20 * 100, 0, 100)  # -10R → 0, +10R → 100
    
    return neg_score * 0.35 + p95_dd_score * 0.35 + p95_ls_score * 0.20 + p5_total_score * 0.10


def _compute_risk_control_score(row: pd.Series, config: SSSConfig) -> float:
    """Compute Risk Control Score (weight: 0.20)."""
    dd = _drawdown_score(row.get("max_drawdown_R", 0))
    ls = _losing_streak_score(row.get("longest_losing_streak", 0))
    al = _avg_loss_score(row.get("avg_loss_R", -1))
    pr = _payoff_score(row.get("payoff_ratio", 0))
    
    return dd * 0.30 + ls * 0.25 + al * 0.20 + pr * 0.25


# ============================================================
# Score mapping functions (metric → 0-100)
# ============================================================

def _trade_count_score(trade_count: int, min_trades: int) -> float:
    """Map trade count to 0-100. 100 at min_trades*2, linear below."""
    if trade_count <= 0:
        return 0.0
    target = min_trades * 2
    return clamp(trade_count / target * 100, 0, 100)


def _win_rate_score(win_rate: float) -> float:
    """Map win rate to 0-100. 100 at >= 70%, linear from 0-70%."""
    if win_rate is None or np.isnan(win_rate):
        return 50.0
    return clamp(win_rate / 0.70 * 100, 0, 100)


def _profit_factor_score(pf: float) -> float:
    """Map profit factor to 0-100. 100 at >= 3.0, linear below."""
    if pf is None or np.isnan(pf) or pf <= 0:
        return 0.0
    return clamp(pf / 3.0 * 100, 0, 100)


def _expectancy_score(expectancy: float) -> float:
    """Map expectancy (avg R) to 0-100. -0.5R → 0, 1.0R → 100, linear."""
    if expectancy is None or np.isnan(expectancy):
        return 50.0
    return clamp((expectancy + 0.5) / 1.5 * 100, 0, 100)


def _drawdown_score(drawdown: float) -> float:
    """Map max drawdown to 0-100. -20R → 0, 0R → 100, linear."""
    if drawdown is None or np.isnan(drawdown):
        return 50.0
    # drawdown is negative or 0
    return clamp((1.0 + drawdown / 20.0) * 100, 0, 100)


def _losing_streak_score(streak: float) -> float:
    """Map losing streak to 0-100. 8+ → 0, 0 → 100, linear."""
    if streak is None or np.isnan(streak):
        return 50.0
    return clamp((1.0 - streak / 8.0) * 100, 0, 100)


def _avg_loss_score(avg_loss: float) -> float:
    """Map avg loss to 0-100. -2R → 0, -0.2R → 100, linear."""
    if avg_loss is None or np.isnan(avg_loss):
        return 50.0
    # avg_loss should be negative
    loss = abs(avg_loss) if avg_loss < 0 else avg_loss * (-1)
    if loss <= 0.2:
        return 100.0
    if loss >= 2.0:
        return 0.0
    return clamp((2.0 - loss) / 1.8 * 100, 0, 100)


def _payoff_score(payoff: float) -> float:
    """Map payoff ratio to 0-100. 0.5 → 0, 3.0 → 100, linear."""
    if payoff is None or np.isnan(payoff) or payoff <= 0:
        return 0.0
    return clamp((payoff - 0.5) / 2.5 * 100, 0, 100)


# ============================================================
# Multiplier / Penalty functions
# ============================================================

def _compute_sample_confidence_multiplier(row: pd.Series, config: SSSConfig) -> float:
    """Compute sample confidence multiplier based on trade count."""
    trade_count = row.get("trade_count", 0)
    min_trades = config.min_trades
    if trade_count >= min_trades:
        return 1.00
    return max(0.50, trade_count / min_trades)


def _compute_recent_loss_penalty(row: pd.Series) -> float:
    """Compute recent loss penalty based on current losing streak."""
    streak = row.get("current_losing_streak", 0)
    if streak is None or np.isnan(streak):
        return 1.00
    streak = int(streak)
    if streak >= 5:
        return 0.75
    elif streak == 4:
        return 0.85
    elif streak == 3:
        return 0.92
    return 1.00


def _compute_mc_tail_risk_penalty(row: pd.Series) -> float:
    """Compute MC tail risk penalty based on probability of drawdown exceeding threshold."""
    prob = row.get("probability_drawdown_exceeds_threshold", 0)
    if prob is None or np.isnan(prob):
        return 1.00
    if prob >= 0.40:
        return 0.75
    elif prob >= 0.25:
        return 0.85
    elif prob >= 0.15:
        return 0.92
    return 1.00


def _compute_edge_concentration_penalty(row: pd.Series, config: SSSConfig) -> float:
    """Compute edge concentration penalty."""
    if not config.edge_concentration.enabled:
        return 1.00
    
    lw = row.get("largest_win_contribution")
    t5 = row.get("top_5_trade_contribution")
    warning = row.get("edge_concentration_warning", False)
    
    if lw is not None and not np.isnan(lw) and lw > 0.50:
        if t5 is not None and not np.isnan(t5) and t5 > 0.75:
            return 0.85
    if warning:
        return 0.90
    return 1.00


# ============================================================
# Drivers, reasons, notes
# ============================================================

def _determine_status(score: float, config: SSSConfig) -> str:
    """Map score to status label."""
    t = config.score_thresholds
    if score >= t.strong_enable:
        return "强开启"
    elif score >= t.medium_enable:
        return "中等开启"
    elif score >= t.weak_enable:
        return "弱开启"
    return "禁用"


def _compute_score_drivers(
    regime_edge: float,
    recent_health: float,
    mc_stability: float,
    risk_control: float,
) -> List[str]:
    """Generate score driver descriptions."""
    drivers = []
    if regime_edge >= 70:
        drivers.append("positive_expectancy" if regime_edge >= 85 else "moderate_edge")
    if recent_health >= 70:
        drivers.append("healthy_recent_performance")
    if mc_stability >= 70:
        drivers.append("healthy_mc_distribution")
    if risk_control >= 70:
        drivers.append("controlled_drawdown")
    
    # Additional details
    if regime_edge >= 80:
        drivers.append("strong_profit_factor" if regime_edge >= 80 else "stable_payoff_ratio")
    
    return drivers


def _compute_penalty_drivers(
    sample_mult: float,
    recent_loss_penalty: float,
    mc_tail_penalty: float,
    edge_penalty: float,
    row: pd.Series,
) -> List[str]:
    """Generate penalty driver descriptions."""
    penalties = []
    if sample_mult < 1.0:
        penalties.append("low_sample_size")
    if recent_loss_penalty < 1.0:
        penalties.append("recent_losing_streak")
    if mc_tail_penalty < 1.0:
        penalties.append("high_mc_tail_drawdown")
    if edge_penalty < 1.0:
        penalties.append("edge_concentration")
    
    # Check for capping warnings
    warnings_str = row.get("warnings", "")
    if isinstance(warnings_str, str):
        if "profit_factor_capped" in warnings_str:
            penalties.append("profit_factor_capped")
        if "payoff_ratio_capped" in warnings_str:
            penalties.append("payoff_ratio_capped")
    
    return penalties


def _determine_primary_reason(
    score: float,
    base_score: float,
    penalties: List[str],
    row: pd.Series,
    config: SSSConfig,
) -> str:
    """Determine primary reason for the enable score.
    
    For disabled strategies, distinguishes between:
    - Low sample (strategy might be fine, not enough data)
    - MC tail risk (high probability of large drawdowns)
    - Edge concentration (too dependent on outlier wins)
    - Truly poor performance (strategy likely ineffective)
    """
    if score >= config.score_thresholds.strong_enable:
        return "regime下表现稳健：长期edge确认、MC尾部风险可控、无严重惩罚"
    elif score >= config.score_thresholds.medium_enable:
        if penalties:
            return f"中等开启：{'、'.join(penalties[:2])}等因素限制了分数"
        return "中等开启：基础指标可接受，部分子分数偏低"
    elif score >= config.score_thresholds.weak_enable:
        if penalties:
            return f"弱开启：{'、'.join(penalties[:2])}等风险因素存在"
        return "弱开启：表现不稳定或样本不足"
    else:
        # Disabled — distinguish root cause
        return _determine_disable_reason(base_score, penalties, row, config)


def _determine_disable_reason(
    base_score: float,
    penalties: List[str],
    row: pd.Series,
    config: SSSConfig,
) -> str:
    """Determine the primary reason a strategy is disabled.
    
    Priority order:
    1. Low sample -> strategy may be fine, data insufficient
    2. MC tail risk -> drawdown probability too high
    3. Edge concentration -> returns driven by outlier trades
    4. Truly poor performance -> base score itself is low
    """
    trade_count = int(row.get("trade_count", 0))
    
    # Low sample is the primary explainer — priority over other penalties
    if "low_sample_size" in penalties:
        if base_score >= config.score_thresholds.medium_enable:
            return (
                f"禁用主因：样本不足（{trade_count} < {config.min_trades}），"
                f"当前结论不代表策略失效。"
                f"Base Score {base_score:.0f} 显示策略在统计层面有 edge，增加样本后可重新评估"
            )
        elif base_score >= config.score_thresholds.weak_enable:
            return (
                f"禁用主因：样本不足（{trade_count} < {config.min_trades}），"
                f"当前结论不代表策略必然失效。"
                f"Base Score {base_score:.0f} 处于边界，建议补充数据后重评"
            )
        else:
            # Low sample + weak base — sample is still the primary blocker
            return (
                f"禁用主因：样本不足（{trade_count} < {config.min_trades}）"
                f"且 Base Score {base_score:.0f} 偏低，"
                f"无法区分「策略失效」与「噪音波动」。建议先补充数据再评估"
            )
    
    # MC tail risk
    if "high_mc_tail_drawdown" in penalties:
        prob = row.get("probability_drawdown_exceeds_threshold", 0)
        prob_str = f"{prob:.1%}" if isinstance(prob, (int, float)) else str(prob)
        return (
            f"禁用主因：Monte Carlo 尾部回撤风险过高。"
            f"P(drawdown > {config.monte_carlo.drawdown_threshold_R}R) = {prob_str}"
        )
    
    # Edge concentration
    if "edge_concentration" in penalties:
        lw = row.get("largest_win_contribution", 0)
        lw_str = f"{lw:.1%}" if isinstance(lw, (int, float)) and not np.isnan(lw) else "?"
        return (
            f"禁用主因：收益过度集中于少数极端盈利交易。"
            f"最大单笔盈利占比 = {lw_str}，不宜依赖总收益判断稳定性"
        )
    
    # Recent losing streak — serious enough to disable when base is borderline
    if "recent_losing_streak" in penalties:
        ls = int(row.get("current_losing_streak", 0))
        return (
            f"禁用主因：当前连亏 {ls} 笔，近期表现严重恶化。"
            f"Base Score {base_score:.0f}，建议暂停观察市场环境是否恢复"
        )
    
    # Truly poor performance
    if base_score < config.score_thresholds.weak_enable:
        return (
            f"综合评分过低（Base Score = {base_score:.0f}）："
            f"长期edge不足或风险控制弱，策略在当前regime下可能失效"
        )
    
    # Fallback
    if "low_sample_size" in penalties:
        return f"禁用：样本不足（{trade_count} < {config.min_trades}），当前结论仅供参考"
    return "禁用：综合评分过低，策略在当前regime下不可靠"


def _compute_risk_notes(
    row: pd.Series,
    penalties: List[str],
    config: SSSConfig,
) -> str:
    """Generate risk notes text."""
    notes = []
    
    if row.get("low_sample_warning"):
        notes.append(f"样本不足（{row.get('trade_count', 0)} < {config.min_trades}），结果仅供参考")
    
    if row.get("edge_concentration_warning"):
        notes.append("该组合可能依赖少数极端行情，不宜仅凭总收益判断稳定性")
    
    if "high_mc_tail_drawdown" in penalties:
        prob = row.get("probability_drawdown_exceeds_threshold", 0)
        notes.append(f"MC尾部风险偏高：P(drawdown > {config.monte_carlo.drawdown_threshold_R}R) = {prob:.1%}")
    
    if "recent_losing_streak" in penalties:
        notes.append(f"当前连亏{int(row.get('current_losing_streak', 0))}笔，近期表现恶化")
    
    if "profit_factor_capped" in penalties:
        notes.append(f"Profit Factor被cap于{config.metric_caps.max_profit_factor}（极端值）")
    
    if "payoff_ratio_capped" in penalties:
        notes.append(f"Payoff Ratio被cap于{config.metric_caps.max_payoff_ratio}（极端值）")
    
    return "; ".join(notes) if notes else ""


def _compute_review_required(
    row: pd.Series,
    penalties: List[str],
    config: SSSConfig,
) -> bool:
    """Determine if review is required."""
    rr = config.review_rules
    
    if rr.low_sample_requires_review and row.get("low_sample_warning", False):
        return True
    
    if rr.edge_concentration_requires_review and row.get("edge_concentration_warning", False):
        return True
    
    prob = row.get("probability_drawdown_exceeds_threshold", 0)
    if prob is not None and prob > rr.mc_drawdown_probability_review_threshold:
        return True
    
    streak = row.get("current_losing_streak", 0)
    if streak and streak >= rr.losing_streak_review_threshold:
        return True
    
    trade_count = row.get("trade_count", 0)
    if trade_count < config.min_trades:
        return True
    
    return False
