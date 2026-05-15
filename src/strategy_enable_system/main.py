"""
CLI Entry Point for Strategy Enable Score System v1.1.
Usage: python -m strategy_enable_system.main --config config.yaml
"""

import sys
import os
import argparse
import logging

# Add src to path for direct execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from strategy_enable_system.config import load_config
from strategy_enable_system.data_loader import load_trades
from strategy_enable_system.metrics import compute_performance_matrix
from strategy_enable_system.monte_carlo import run_monte_carlo
from strategy_enable_system.scoring import compute_enable_scores
from strategy_enable_system.reporting import generate_report
from strategy_enable_system.recommendations import generate_recommendations, render_recommendations_summary

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Strategy Enable Score System v1.1"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml)",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Override auto-generated run directory name (slug).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output_dir from config.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing run directory.",
    )
    parser.add_argument(
        "--legacy-output",
        action="store_true",
        help="Use legacy output mode (write directly to output_dir, no subdirectories).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON at the end.",
    )
    args = parser.parse_args()

    config_path = args.config
    logger.info(f"Loading config from {config_path}")
    config = load_config(config_path)
    # Store config path for metadata (non-invasive)
    config._config_path = os.path.abspath(config_path)

    # Apply CLI overrides
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.run_name is not None:
        config.report_output.run_name = args.run_name
    if args.overwrite:
        config.report_output.overwrite = True
    if args.legacy_output:
        config.report_output.run_mode = "legacy"

    logger.info("Loading trades...")
    trades = load_trades(config)
    logger.info(f"Loaded {len(trades)} trades, {trades['strategy_name'].nunique()} strategies, {trades['regime'].nunique()} regimes")

    logger.info("Computing performance matrix...")
    pm = compute_performance_matrix(trades, config)
    logger.info(f"Performance matrix: {len(pm)} (strategy, regime) combinations")

    logger.info("Running Monte Carlo simulations...")
    mc = run_monte_carlo(trades, config)
    logger.info(f"Monte Carlo: {len(mc)} combinations simulated")

    logger.info("Computing enable scores...")
    scores = compute_enable_scores(pm, mc, config)
    logger.info(f"Enable scores: {len(scores)} combinations scored")

    logger.info("Generating recommendations...")
    rec_result = generate_recommendations(pm, scores, trades, config.recommendations)
    if rec_result.recommendations:
        logger.info(f"Generated {len(rec_result.recommendations)} recommendations")
    else:
        logger.info("No recommendations generated (module disabled or no triggers)")

    logger.info("Generating reports...")
    md_path = generate_report(pm, mc, scores, trades, config, rec_result)
    report_dir = os.path.dirname(md_path)

    logger.info(f"Done! Report: {md_path}")

    # Quick summary
    status_counts = {}
    if "status" in scores.columns:
        status_counts = scores["status"].value_counts().to_dict()
        logger.info("Status breakdown:")
        for status_name in ["强开启", "中等开启", "弱开启", "禁用"]:
            logger.info(f"  {status_name}: {status_counts.get(status_name, 0)}")

    # JSON mode output (stable schema for DMC integration)
    if args.json:
        import json
        json_out = {
            "status": "ok",
            "report_dir": report_dir,
            "run_mode": config.report_output.run_mode,
            "outputs": {
                "summary_report": md_path,
                "performance_matrix": os.path.join(report_dir, "performance_matrix.csv"),
                "enable_scores": os.path.join(report_dir, "enable_score.csv"),
                "monte_carlo_results": os.path.join(report_dir, "monte_carlo_results.csv"),
                "run_metadata": os.path.join(report_dir, "run_metadata.yaml") if config.report_output.run_mode != "legacy" else None,
            },
            "total_trades": len(trades),
            "strategy_count": trades["strategy_name"].nunique() if "strategy_name" in trades.columns else 0,
            "status_counts": status_counts,
            "warnings": [],
        }
        # JSON to stdout only; everything else on stderr via logging
        sys.stdout.write(json.dumps(json_out, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
