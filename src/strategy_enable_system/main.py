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
    args = parser.parse_args()

    config_path = args.config
    logger.info(f"Loading config from {config_path}")
    config = load_config(config_path)

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

    logger.info("Generating reports...")
    md_path = generate_report(pm, mc, scores, trades, config)

    logger.info(f"Done! Report: {md_path}")
    logger.info("Output files:")
    for fname in ["performance_matrix.csv", "monte_carlo_results.csv", "enable_score.csv", "summary_report.md"]:
        logger.info(f"  - {config.output_dir}/{fname}")

    # Quick summary
    if "status" in scores.columns:
        status_counts = scores["status"].value_counts()
        logger.info("Status breakdown:")
        for status_name in ["强开启", "中等开启", "弱开启", "禁用"]:
            logger.info(f"  {status_name}: {status_counts.get(status_name, 0)}")


if __name__ == "__main__":
    main()
