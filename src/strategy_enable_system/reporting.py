"""
Reporting Module for Strategy Enable Score System v1.1.
Outputs CSV files and Markdown summary report with regime snapshot,
layered regime, edge concentration detail, and risk category analysis.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict

from .config import SSSConfig


def generate_report(
    performance_matrix: pd.DataFrame,
    monte_carlo_results: pd.DataFrame,
    enable_scores: pd.DataFrame,
    trades: pd.DataFrame,
    config: SSSConfig,
) -> str:
    """Generate all output files: CSVs and Markdown summary.
    
    Args:
        performance_matrix: Regime performance matrix.
        monte_carlo_results: Monte Carlo results.
        enable_scores: Enable score results.
        trades: Original standardized trades DataFrame (for distribution stats).
        config: SSSConfig object.
    
    Returns:
        str: Path to the generated summary_report.md.
    """
    os.makedirs(config.output_dir, exist_ok=True)
    
    # Write CSVs
    pm_path = os.path.join(config.output_dir, "performance_matrix.csv")
    mc_path = os.path.join(config.output_dir, "monte_carlo_results.csv")
    es_path = os.path.join(config.output_dir, "enable_score.csv")
    
    performance_matrix.to_csv(pm_path, index=False)
    monte_carlo_results.to_csv(mc_path, index=False)
    enable_scores.to_csv(es_path, index=False)
    
    # Generate Markdown summary
    md_content = _build_markdown_summary(performance_matrix, monte_carlo_results, enable_scores, trades, config)
    md_path = os.path.join(config.output_dir, "summary_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    return md_path


def _build_markdown_summary(
    pm: pd.DataFrame,
    mc: pd.DataFrame,
    es: pd.DataFrame,
    trades: pd.DataFrame,
    config: SSSConfig,
) -> str:
    """Build the Markdown summary report."""
    lines: List[str] = []
    
    _h(lines, 1, "Strategy Enable Score System v1.1 — Summary Report")
    lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**数据文件：** {', '.join(config.input_path)}")
    lines.append("")
    
    # ========================
    # Overview table
    # ========================
    _h(lines, 2, "策略评分总览")
    lines.append("")
    overview_cols = [
        "strategy_name", "regime", "enable_score",
        "final_activation_score", "status", "review_required",
        "low_sample_warning", "edge_concentration_warning"
    ]
    available_cols = [c for c in overview_cols if c in es.columns]
    overview = es[available_cols].sort_values("enable_score", ascending=False)
    lines.append(_df_to_markdown_table(overview))
    lines.append("")
    
    # ========================
    # Status breakdown
    # ========================
    _h(lines, 2, "状态分布")
    if "status" in es.columns:
        status_counts = es["status"].value_counts()
        for status_name in ["强开启", "中等开启", "弱开启", "禁用"]:
            count = status_counts.get(status_name, 0)
            lines.append(f"- **{status_name}：** {count} 个组合")
    lines.append("")
    
    # ========================
    # Enable recommendations
    # ========================
    _h(lines, 2, "策略开启建议")
    
    strong = es[es["status"] == "强开启"] if "status" in es.columns else pd.DataFrame()
    medium = es[es["status"] == "中等开启"] if "status" in es.columns else pd.DataFrame()
    weak = es[es["status"] == "弱开启"] if "status" in es.columns else pd.DataFrame()
    disabled = es[es["status"] == "禁用"] if "status" in es.columns else pd.DataFrame()
    
    def _print_recommendation(rows, emoji, label):
        if len(rows) > 0:
            _h(lines, 3, f"{emoji} {label}")
            for _, row in rows.iterrows():
                lines.append(f"- **{row['strategy_name']}** @ {row['regime']} — Score: {row['enable_score']:.1f}")
                if row.get("primary_reason"):
                    lines.append(f"  > {row['primary_reason']}")
        else:
            lines.append(f"无{label}组合。")
    
    _print_recommendation(strong, "✅", "强开启")
    _print_recommendation(medium, "🟡", "中等开启")
    _print_recommendation(weak, "🟠", "弱开启")
    _print_recommendation(disabled, "🔴", "禁用")
    lines.append("")
    
    # ========================
    # P1-4: Four risk categories
    # ========================
    _h(lines, 2, "风险分类诊断")
    lines.append("")
    
    _build_risk_categories(lines, es, pm, mc, config)
    
    # ========================
    # Risk warnings (detailed)
    # ========================
    _h(lines, 2, "风险详情")
    
    # Low sample warnings
    _build_low_sample_section(lines, es, pm, config)
    
    # P1-3: Edge concentration with trigger details
    _build_edge_concentration_section(lines, es, pm, config)
    
    # MC tail risk
    _build_mc_tail_risk_section(lines, es, mc, config)
    
    # Recent deterioration
    _build_recent_deterioration_section(lines, es, pm, config)
    
    # Review required
    _build_review_required_section(lines, es)
    
    # ========================
    # P1-1: Regime Snapshot ID Distribution
    # ========================
    _h(lines, 2, "Market State Snapshot 分布 (regime_snapshot_id)")
    lines.append("")
    _build_snapshot_distribution(lines, trades, es, config)
    
    # ========================
    # P1-2: Layered Regime Field Distribution
    # ========================
    _h(lines, 2, "分层 Regime 字段分布")
    lines.append("")
    _build_layered_regime_distribution(lines, trades, es, config)
    
    # ========================
    # Market Opportunity placeholder
    # ========================
    _h(lines, 2, "Market Opportunity Score")
    lines.append("v1.1 中 Market Opportunity Score 为 placeholder，默认值 1.0。")
    lines.append(f"Final Activation Score = Enable Score × {config.market_opportunity.default_score}")
    lines.append("")
    
    # ========================
    # Detailed performance table
    # ========================
    _h(lines, 2, "Regime 表现详情")
    pm_display_cols = [
        "strategy_name", "regime", "trade_count", "win_rate",
        "avg_R", "profit_factor", "max_drawdown_R", "payoff_ratio",
        "longest_losing_streak"
    ]
    available_pm = [c for c in pm_display_cols if c in pm.columns]
    pm_display = pm[available_pm].copy()
    for col in ["win_rate", "avg_R", "profit_factor"]:
        if col in pm_display.columns:
            pm_display[col] = pm_display[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    if "max_drawdown_R" in pm_display.columns:
        pm_display["max_drawdown_R"] = pm_display["max_drawdown_R"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    if "payoff_ratio" in pm_display.columns:
        pm_display["payoff_ratio"] = pm_display["payoff_ratio"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    lines.append(_df_to_markdown_table(pm_display))
    lines.append("")
    
    # ========================
    # Monte Carlo summary
    # ========================
    _h(lines, 2, "Monte Carlo 风险验证摘要")
    mc_display_cols = [
        "strategy_name", "regime", "median_total_R",
        "p5_total_R", "p95_max_drawdown_R",
        "probability_of_negative_total_R",
        "probability_drawdown_exceeds_threshold"
    ]
    available_mc = [c for c in mc_display_cols if c in mc.columns]
    mc_display = mc[available_mc].copy()
    for col in ["median_total_R", "p5_total_R", "p95_max_drawdown_R"]:
        if col in mc_display.columns:
            mc_display[col] = mc_display[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    for col in ["probability_of_negative_total_R", "probability_drawdown_exceeds_threshold"]:
        if col in mc_display.columns:
            mc_display[col] = mc_display[col].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "")
    lines.append(_df_to_markdown_table(mc_display))
    lines.append("")
    
    # ========================
    # P2-1: Time Under Water / Recovery 风险
    # ========================
    _build_tuw_section(lines, pm, config)
    
    # ========================
    # Footer
    # ========================
    lines.append("---")
    lines.append("")
    lines.append("### 风险分类说明")
    lines.append("| 分类 | 判断标准 | 含义 |")
    lines.append("|------|---------|------|")
    lines.append("| **样本不足** | trade_count < min_trades | 当前数据不足以做出可靠结论 |")
    lines.append("| **策略可能失效** | Base Score 低（长期指标恶化，负期望值、PF<1） | 策略在当前 regime 下可能不再有效 |")
    lines.append("| **市场暂时无机会** | Recent Health 低但 Regime Edge 仍高 | 近期表现差可能是市场环境问题，非策略失效 |")
    lines.append("| **极端盈利依赖** | Edge Concentration Warning 触发 | 收益过度依赖少数极端交易，稳定性存疑 |")
    lines.append("| **MC 尾部风险过高** | 模拟路径中高概率出现大幅回撤 | 即使长期 edge 存在，尾部风险不可接受 |")
    lines.append("")
    lines.append("*Generated by Strategy Enable Score System v1.1*")
    
    return "\n".join(lines)


# ============================================================
# P1-4: Risk Category Diagnosis
# ============================================================

def _build_risk_categories(
    lines: List[str],
    es: pd.DataFrame,
    pm: pd.DataFrame,
    mc: pd.DataFrame,
    config: SSSConfig,
):
    """Categorize each (strategy, regime) into risk types."""
    if es.empty:
        lines.append("*(no data)*")
        return
    
    # Merge for full context
    ctx = es.merge(
        pm[["strategy_name", "regime", "trade_count", "current_losing_streak", "max_drawdown_R"]],
        on=["strategy_name", "regime"], how="left"
    )
    if "probability_drawdown_exceeds_threshold" not in ctx.columns:
        ctx = ctx.merge(
            mc[["strategy_name", "regime", "probability_drawdown_exceeds_threshold"]],
            on=["strategy_name", "regime"], how="left"
        )
    
    sample_insufficient = []
    strategy_failing = []
    market_no_opportunity = []
    extreme_dependency = []
    mc_tail_risk = []
    healthy = []
    
    for _, row in ctx.iterrows():
        has_low_sample = row.get("low_sample_warning", False)
        has_edge_conc = row.get("edge_concentration_warning", False)
        mc_prob = row.get("probability_drawdown_exceeds_threshold", 0) or 0
        has_mc_risk = mc_prob > 0.25
        
        # Extract base score context from enable_score and penalty_drivers
        penalties = str(row.get("penalty_drivers", ""))
        enable_score = row.get("enable_score", 0)
        
        # Regime edge estimation (use enable_score vs penalties as proxy)
        has_low_base = "low_sample_size" not in penalties and enable_score < config.score_thresholds.weak_enable
        
        # Recent health check
        current_ls = row.get("current_losing_streak", 0) or 0
        
        combo_name = f"{row['strategy_name']} @ {row['regime']}"
        
        # Categorize
        if has_low_sample:
            sample_insufficient.append(combo_name)
        
        if has_mc_risk and enable_score < 50:
            mc_tail_risk.append(combo_name)
        
        if has_edge_conc and enable_score < 50:
            extreme_dependency.append(combo_name)
        
        if has_low_base and not has_low_sample:
            strategy_failing.append(combo_name)
        
        if current_ls >= 3 and enable_score >= config.score_thresholds.weak_enable:
            market_no_opportunity.append(combo_name)
        
        if enable_score >= config.score_thresholds.medium_enable and not has_low_sample:
            healthy.append(combo_name)
    
    # Print categories
    _h(lines, 3, "📊 样本不足")
    if sample_insufficient:
        lines.append(f"以下 {len(sample_insufficient)} 个组合因样本不足导致评分降低——**不代表策略失效**：")
        for name in sample_insufficient:
            lines.append(f"- {name}")
        lines.append(f"> 建议：收集 ≥ {config.min_trades} 笔交易后重新评估。")
    else:
        lines.append("所有组合样本充足。")
    lines.append("")
    
    _h(lines, 3, "❌ 策略可能失效")
    if strategy_failing:
        lines.append(f"以下组合 Base Score 低（长期指标恶化），**策略在当前 regime 下可能不再有效**：")
        for name in strategy_failing:
            lines.append(f"- {name}")
    else:
        lines.append("无策略失效信号。所有低分组合均由样本不足或惩罚乘数驱动。")
    lines.append("")
    
    _h(lines, 3, "🌤️ 市场暂时无机会")
    if market_no_opportunity:
        lines.append("以下组合 Recent Health 较差但长期 Regime Edge 仍存在——**可能是市场环境问题**：")
        for name in market_no_opportunity:
            lines.append(f"- {name}")
        lines.append("> 建议：观察市场状态是否恢复后再开启。")
    else:
        lines.append("无此类别组合。")
    lines.append("")
    
    _h(lines, 3, "🎯 极端盈利依赖")
    if extreme_dependency:
        lines.append("以下组合收益过度依赖少数极端交易——**不宜仅凭总收益判断稳定性**：")
        for name in extreme_dependency:
            lines.append(f"- {name}")
    else:
        lines.append("无极端盈利依赖问题。")
    lines.append("")
    
    _h(lines, 3, "📉 MC 尾部风险过高")
    if mc_tail_risk:
        lines.append("以下组合 Monte Carlo 模拟显示高概率大幅回撤：")
        for name in mc_tail_risk:
            lines.append(f"- {name}")
    else:
        lines.append("无 MC 尾部风险过高组合。")
    lines.append("")


# ============================================================
# Risk detail sections
# ============================================================

def _build_low_sample_section(lines, es, pm, config):
    if "low_sample_warning" not in es.columns:
        return
    low_sample = es[es["low_sample_warning"] == True]
    if len(low_sample) == 0:
        return
    
    lines.append(f"### ⚠️ 样本不足（< {config.min_trades}笔）")
    for _, row in low_sample.iterrows():
        tc = pm.loc[(pm["strategy_name"] == row["strategy_name"]) & (pm["regime"] == row["regime"]), "trade_count"]
        count = tc.values[0] if len(tc) > 0 else "?"
        lines.append(f"- **{row['strategy_name']}** @ {row['regime']} — {count} 笔交易")
    lines.append("")


# ============================================================
# P1-3: Edge concentration with trigger details
# ============================================================

def _build_edge_concentration_section(lines, es, pm, config):
    if "edge_concentration_warning" not in es.columns:
        return
    edge_conc = es[es["edge_concentration_warning"] == True]
    if len(edge_conc) == 0:
        return
    
    lines.append("### ⚠️ Edge Concentration 风险")
    lines.append("以下组合可能依赖少数极端行情。触发详情：")
    lines.append("")
    
    for _, es_row in edge_conc.iterrows():
        strat, regime = es_row["strategy_name"], es_row["regime"]
        pm_match = pm[(pm["strategy_name"] == strat) & (pm["regime"] == regime)]
        if len(pm_match) == 0:
            continue
        pm_row = pm_match.iloc[0]
        
        triggers = []
        lw = pm_row.get("largest_win_contribution")
        t5 = pm_row.get("top_5_trade_contribution")
        t10 = pm_row.get("top_10_percent_trade_contribution")
        
        if lw is not None and not (isinstance(lw, float) and np.isnan(lw)):
            triggers.append(f"最大单笔盈利占比 = {lw:.1%}" + (" ⚠️" if lw > config.edge_concentration.largest_win_warning_threshold else ""))
        else:
            triggers.append("最大单笔盈利占比 = N/A（无正盈利交易）⚠️")
        
        if t5 is not None and not (isinstance(t5, float) and np.isnan(t5)):
            triggers.append(f"Top 5 盈利占比 = {t5:.1%}" + (" ⚠️" if t5 > config.edge_concentration.top_5_warning_threshold else ""))
        else:
            triggers.append("Top 5 盈利占比 = N/A")
        
        if t10 is not None and not (isinstance(t10, float) and np.isnan(t10)):
            triggers.append(f"Top 10% 盈利占比 = {t10:.1%}" + (" ⚠️" if t10 > config.edge_concentration.top_10_percent_warning_threshold else ""))
        else:
            triggers.append("Top 10% 盈利占比 = N/A")
        
        gini = pm_row.get("gini_pnl_R")
        if gini is not None and not (isinstance(gini, float) and np.isnan(gini)):
            triggers.append(f"Gini (正收益) = {gini:.2f}")
        
        lines.append(f"- **{strat}** @ {regime}")
        for trigger in triggers:
            lines.append(f"  - {trigger}")
    lines.append("")


def _build_mc_tail_risk_section(lines, es, mc, config):
    merged = es.merge(
        mc[["strategy_name", "regime", "probability_drawdown_exceeds_threshold"]],
        on=["strategy_name", "regime"], how="left"
    )
    high_mc = merged[merged["probability_drawdown_exceeds_threshold"] > 0.25]
    if len(high_mc) == 0:
        return
    
    lines.append("### ⚠️ Monte Carlo 尾部风险偏高")
    for _, row in high_mc.iterrows():
        prob = row.get("probability_drawdown_exceeds_threshold", "?")
        if isinstance(prob, float):
            lines.append(f"- **{row['strategy_name']}** @ {row['regime']} — P(drawdown > {config.monte_carlo.drawdown_threshold_R}R) = {prob:.1%}")
        else:
            lines.append(f"- **{row['strategy_name']}** @ {row['regime']}")
    lines.append("")


def _build_recent_deterioration_section(lines, es, pm, config):
    merged = es.merge(
        pm[["strategy_name", "regime", "current_losing_streak"]],
        on=["strategy_name", "regime"], how="left"
    )
    losing = merged[merged["current_losing_streak"] >= 3]
    if len(losing) == 0:
        return
    
    lines.append("### ⚠️ 近期表现恶化")
    for _, row in losing.iterrows():
        ls = int(row["current_losing_streak"]) if pd.notna(row.get("current_losing_streak")) else "?"
        es_row = es[(es["strategy_name"] == row["strategy_name"]) & (es["regime"] == row["regime"])]
        base_note = ""
        if len(es_row) > 0:
            p = str(es_row.iloc[0].get("penalty_drivers", ""))
            status_val = es_row.iloc[0].get("status", "")
            if "low_sample_size" not in p and status_val not in ["禁用"]:
                base_note = " — 可能为市场暂时无机会"
        lines.append(f"- **{row['strategy_name']}** @ {row['regime']} — 当前连亏 {ls} 笔{base_note}")
    if len(losing) > 0:
        lines.append("> 注意：Recent Health 恶化只降权不 hard-ban。如长期 Regime Edge 仍健康，可能为市场环境问题。")
    lines.append("")


def _build_review_required_section(lines, es):
    if "review_required" not in es.columns:
        return
    review = es[es["review_required"] == True]
    if len(review) == 0:
        return
    
    lines.append(f"### 🔍 需要人工复核（{len(review)} 个组合）")
    for _, row in review.iterrows():
        risk = row.get("risk_notes", "")
        lines.append(f"- **{row['strategy_name']}** @ {row['regime']} — Score: {row['enable_score']:.1f}")
        if risk:
            lines.append(f"  > {risk}")
    lines.append("")


# ============================================================
# P2-1: Time Under Water / Recovery Section
# ============================================================

def _build_tuw_section(lines, pm, config):
    """Add Time Under Water and Recovery metrics to the summary."""
    tuw_fields = ["time_under_water_ratio", "max_recovery_trades", "average_recovery_trades"]
    available = [f for f in tuw_fields if f in pm.columns]
    
    if not available:
        return
    
    _h(lines, 2, "Time Under Water / Recovery 风险")
    lines.append("")
    lines.append("Time Under Water Ratio 衡量策略在亏损回补中煎熬的时间比例；")
    lines.append("Recovery Trades 衡量从回撤到重新创新高所经历的笔数。")
    lines.append("")
    
    # Sort by TUW ratio descending (worst first)
    pm_display = pm[["strategy_name", "regime", "trade_count"] + available].copy()
    
    # Find high TUW combos
    if "time_under_water_ratio" in pm_display.columns:
        pm_display = pm_display.sort_values("time_under_water_ratio", ascending=False)
        
        high_tuw = pm_display[pm_display["time_under_water_ratio"] > 0.5]
        if len(high_tuw) > 0:
            lines.append(f"### ⚠️ 高 TUW 组合（TUW > 50%，共 {len(high_tuw)} 个）")
            lines.append("")
            for _, row in high_tuw.iterrows():
                tuw = row["time_under_water_ratio"]
                mr = row.get("max_recovery_trades")
                ar = row.get("average_recovery_trades")
                mr_str = f"{int(mr)}" if pd.notna(mr) else "N/A"
                ar_str = f"{ar:.1f}" if pd.notna(ar) else "N/A"
                low_note = " (样本少，参考有限)" if row["trade_count"] < config.min_trades else ""
                lines.append(
                    f"- **{row['strategy_name']}** @ {row['regime']} — "
                    f"TUW={tuw:.1%}, max_recovery={mr_str}笔, avg_recovery={ar_str}笔{low_note}"
                )
            lines.append("")
        
        # Slow recovery combos
        if "max_recovery_trades" in pm_display.columns:
            slow = pm_display[pm_display["max_recovery_trades"] > 20]
            if len(slow) > 0:
                lines.append(f"### 🐢 恢复缓慢组合（max_recovery > 20笔，共 {len(slow)} 个）")
                lines.append("")
                for _, row in slow.iterrows():
                    mr = row.get("max_recovery_trades")
                    mr_str = f"{int(mr)}" if pd.notna(mr) else "N/A"
                    lines.append(f"- **{row['strategy_name']}** @ {row['regime']} — 最长恢复需 {mr_str} 笔交易")
                lines.append("")
        
        # Full table
        lines.append("### 完整 TUW / Recovery 一览")
        lines.append("")
        display = pm_display.copy()
        if "time_under_water_ratio" in display.columns:
            display["time_under_water_ratio"] = display["time_under_water_ratio"].apply(
                lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
            )
        if "max_recovery_trades" in display.columns:
            display["max_recovery_trades"] = display["max_recovery_trades"].apply(
                lambda x: f"{int(x)}" if pd.notna(x) else "N/A"
            )
        if "average_recovery_trades" in display.columns:
            display["average_recovery_trades"] = display["average_recovery_trades"].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
            )
        lines.append(_df_to_markdown_table(display))
    
    lines.append("")


# ============================================================
# P1-1: Regime Snapshot ID Distribution
# ============================================================

def _build_snapshot_distribution(
    lines: List[str],
    trades: pd.DataFrame,
    es: pd.DataFrame,
    config: SSSConfig,
):
    """Show regime_snapshot_id distribution per (strategy_name, regime)."""
    if "regime_snapshot_id" not in trades.columns:
        lines.append("*(regime_snapshot_id 字段不存在于输入数据中)*")
        return
    
    lines.append("每个 (strategy, regime) 组合内的 market state snapshot 分布：")
    lines.append("")
    
    for _, es_row in es.iterrows():
        strat, regime = es_row["strategy_name"], es_row["regime"]
        mask = (trades["strategy_name"] == strat) & (trades["regime"] == regime)
        subset = trades[mask]
        
        if len(subset) == 0:
            continue
        
        snap_counts = subset["regime_snapshot_id"].value_counts()
        total = len(subset)
        
        lines.append(f"**{strat}** @ {regime} ({total} 笔交易)：")
        for snap_id, count in snap_counts.items():
            pct = count / total * 100
            snap_display = snap_id if pd.notna(snap_id) and snap_id != "" else "unknown"
            lines.append(f"- {snap_display}：{count} ({pct:.0f}%)")
        lines.append("")


# ============================================================
# P1-2: Layered Regime Field Distribution
# ============================================================

def _build_layered_regime_distribution(
    lines: List[str],
    trades: pd.DataFrame,
    es: pd.DataFrame,
    config: SSSConfig,
):
    """Show structure_state, volatility_state, orderflow_state, macro_state distribution.
    
    Displays per-regime (across all strategies) to reveal if a regime
    contains too many mixed states.
    """
    layered_fields = ["structure_state", "volatility_state", "orderflow_state", "macro_state"]
    available = [f for f in layered_fields if f in trades.columns]
    
    if not available:
        lines.append("*(分层 regime 字段不存在于输入数据中)*")
        return
    
    lines.append("以下展示每个 regime 内部的分层标签混合程度。")
    lines.append("如果某个 regime 内状态过于混杂，说明该 regime 定义可能需要细化。")
    lines.append("")
    
    regimes = sorted(trades["regime"].dropna().unique())
    
    for regime in regimes:
        subset = trades[trades["regime"] == regime]
        total = len(subset)
        
        lines.append(f"### regime = **{regime}** ({total} 笔交易)")
        lines.append("")
        
        for field in available:
            value_counts = subset[field].value_counts()
            parts = []
            for val, count in value_counts.items():
                val_display = val if pd.notna(val) and val != "" else "unknown"
                parts.append(f"{val_display} ({count}, {count/total*100:.0f}%)")
            lines.append(f"- **{field}：** " + " / ".join(parts))
        
        lines.append("")


# ============================================================
# Helper functions
# ============================================================

def _h(lines: List[str], level: int, text: str):
    """Add a heading to the markdown lines."""
    prefix = "#" * level
    lines.append(f"{prefix} {text}")


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a Markdown table string."""
    if df.empty:
        return "*(no data)*"
    
    headers = list(df.columns)
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "|" + "|".join([" --- " for _ in headers]) + "|"
    
    rows = []
    for _, row in df.iterrows():
        cells = [str(v) if pd.notna(v) else "" for v in row]
        rows.append("| " + " | ".join(cells) + " |")
    
    return header_line + "\n" + sep_line + "\n" + "\n".join(rows)
