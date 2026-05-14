"""
CoinGlass Fetch Orchestrator for Strategy Enable Score System v1.1 (P2-7).

Supports three modes:
- dry-run: Prints planned endpoints/paths without any network requests or file writes.
- mock: Generates synthetic raw JSON + processed CSV + audit report (no network).
- live: Calls CoinGlass API (requires allow_network=true + API key).

Run standalone:
  PYTHONPATH=src python -m strategy_enable_system.coinglass_fetch --config config.yaml --dry-run
  PYTHONPATH=src python -m strategy_enable_system.coinglass_fetch --config config.yaml --mock
  PYTHONPATH=src python -m strategy_enable_system.coinglass_fetch --config config.yaml --live
"""

import os
import json
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np

from .config import load_config, CoinGlassClientConfig
from .coinglass_client import CoinGlassClient

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint definitions
# ---------------------------------------------------------------------------

ENDPOINT_DEFS = [
    {
        "key": "open_interest_aggregated",
        "path": "/api/futures/open-interest/aggregated-history",
        "params_fn": lambda c: {"symbol": None, "interval": c.futures.interval, "limit": c.futures.limit, "unit": "usd"},
        "file_suffix": "{symbol}_oi_agg",
        "per_symbol": True,
    },
    {
        "key": "funding_oi_weight",
        "path": "/api/futures/funding-rate/oi-weight-history",
        "params_fn": lambda c: {"symbol": None, "interval": c.futures.interval, "limit": c.futures.limit},
        "file_suffix": "{symbol}_funding_oiw",
        "per_symbol": True,
    },
    {
        "key": "taker_buy_sell_aggregated",
        "path": "/api/futures/aggregated-taker-buy-sell-volume/history",
        "params_fn": lambda c: {"exchange_list": c.futures.exchange_list, "symbol": None, "interval": c.futures.intraday_interval, "limit": c.futures.limit, "unit": "usd"},
        "file_suffix": "{symbol}_taker_agg",
        "per_symbol": True,
        "exchange_list": True,
    },
    {
        "key": "bitcoin_etf_flow",
        "path": "/api/etf/bitcoin/flow-history",
        "params_fn": lambda c: {},
        "file_suffix": "btc_etf_flow",
        "per_symbol": False,
        "symbol_override": "BTC",
    },
    {
        "key": "ethereum_etf_flow",
        "path": "/api/etf/ethereum/flow-history",
        "params_fn": lambda c: {},
        "file_suffix": "eth_etf_flow",
        "per_symbol": False,
        "symbol_override": "ETH",
    },
    {
        "key": "financial_calendar",
        "path": "/api/calendar/economic-data",
        "params_fn": lambda c: _cal_params(c),
        "file_suffix": "calendar_economic",
        "per_symbol": False,
        "symbol_override": "GLOBAL",
    },
]


def _cal_params(config: CoinGlassClientConfig) -> dict:
    now = datetime.utcnow()
    return {
        "start_time": int((now - timedelta(days=config.calendar.lookback_days)).timestamp()),
        "end_time": int((now + timedelta(days=config.calendar.lookahead_days)).timestamp()),
        "language": config.calendar.language,
    }


def _endpoint_enabled(ep_def: dict, config: CoinGlassClientConfig) -> bool:
    """Check if an endpoint is enabled in config.
    
    If config.fetcher_endpoints is set (non-empty list), only endpoints
    whose key is in that list are enabled.
    """
    key = ep_def["key"]
    # CLI override: explicit endpoint filter
    if config.fetcher_endpoints:
        return key in config.fetcher_endpoints
    if key in ("open_interest_aggregated", "funding_oi_weight", "taker_buy_sell_aggregated"):
        enabled = config.futures.endpoints.get(key, True)
        return bool(enabled)
    if key in ("bitcoin_etf_flow",):
        enabled = config.etf.endpoints.get("bitcoin_flow_history", True)
        return bool(enabled)
    if key in ("ethereum_etf_flow",):
        enabled = config.etf.endpoints.get("ethereum_flow_history", True)
        return bool(enabled)
    if key == "financial_calendar":
        return config.calendar.enabled
    return True


# ---------------------------------------------------------------------------
# Raw file path helpers
# ---------------------------------------------------------------------------

def _raw_path(config: CoinGlassClientConfig, ep_def: dict, symbol: Optional[str] = None) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = ep_def["file_suffix"]
    if symbol:
        suffix = suffix.replace("{symbol}", symbol)
    if config.output_suffix:
        suffix = f"{suffix}_{config.output_suffix}"
    fname = f"{suffix}_{ts}.json"
    return os.path.join(config.cache_dir, "raw", fname)


def _processed_path(config: CoinGlassClientConfig, ep_def: dict, symbol: Optional[str] = None) -> str:
    suffix = ep_def["file_suffix"]
    if symbol:
        suffix = suffix.replace("{symbol}", symbol)
    if config.output_suffix:
        suffix = f"{suffix}_{config.output_suffix}"
    return os.path.join(config.cache_dir, "processed", f"{suffix}.csv")


# ---------------------------------------------------------------------------
# Mock data generators
# ---------------------------------------------------------------------------

def _mock_oi_data(symbol: str) -> List[dict]:
    records = []
    base = datetime(2026, 1, 1)
    for i in range(30):
        ts = int((base + timedelta(days=i)).timestamp() * 1000)
        oi = 10_000_000_000 + i * 50_000_000 + np.random.randint(-200_000_000, 200_000_000)
        records.append({
            "time": ts,
            "open": oi - 10_000_000,
            "high": oi + 20_000_000,
            "low": oi - 30_000_000,
            "close": oi,
        })
    return records


def _mock_funding_data(symbol: str) -> List[dict]:
    records = []
    base = datetime(2026, 1, 1)
    for i in range(30):
        ts = int((base + timedelta(days=i)).timestamp() * 1000)
        rate = 0.0001 + np.random.uniform(-0.0005, 0.0005)
        records.append({"time": ts, "open": rate, "high": rate + 0.0001, "low": rate - 0.0001, "close": rate})
    return records


def _mock_taker_data(symbol: str) -> List[dict]:
    records = []
    base = datetime(2026, 1, 1)
    for i in range(50):
        ts = int((base + timedelta(hours=i)).timestamp() * 1000)
        buy = 50_000_000 + np.random.randint(-20_000_000, 20_000_000)
        sell = 50_000_000 + np.random.randint(-20_000_000, 20_000_000)
        records.append({"time": ts, "aggregated_buy_volume_usd": buy, "aggregated_sell_volume_usd": sell})
    return records


def _mock_etf_data(symbol: str) -> List[dict]:
    records = []
    base = datetime(2026, 1, 1)
    for i in range(30):
        ts = int((base + timedelta(days=i)).timestamp() * 1000)
        flow = np.random.uniform(-200_000_000, 500_000_000)
        price = 100_000 if symbol == "BTC" else 3_500
        records.append({"timestamp": ts, "flow_usd": round(flow, 0), "price_usd": price})
    return records


def _mock_calendar_data(symbol: str = "") -> List[dict]:
    return [
        {
            "publish_timestamp": int((datetime(2026, 1, 12, 13, 30)).timestamp()),
            "calendar_name": "CPI MoM",
            "country_code": "US",
            "country_name": "United States",
            "data_effect": "",
            "importance_level": 3,
            "has_exact_publish_time": 1,
        },
        {
            "publish_timestamp": int((datetime(2026, 1, 15, 13, 30)).timestamp()),
            "calendar_name": "Initial Jobless Claims",
            "country_code": "US",
            "country_name": "United States",
            "data_effect": "",
            "importance_level": 2,
            "has_exact_publish_time": 1,
        },
        {
            "publish_timestamp": int((datetime(2026, 1, 29, 19, 0)).timestamp()),
            "calendar_name": "FOMC Statement",
            "country_code": "US",
            "country_name": "United States",
            "data_effect": "",
            "importance_level": 3,
            "has_exact_publish_time": 1,
        },
    ]


MOCK_GENERATORS = {
    "open_interest_aggregated": _mock_oi_data,
    "funding_oi_weight": _mock_funding_data,
    "taker_buy_sell_aggregated": _mock_taker_data,
    "bitcoin_etf_flow": _mock_etf_data,
    "ethereum_etf_flow": _mock_etf_data,
    "financial_calendar": _mock_calendar_data,
}


# ---------------------------------------------------------------------------
# Processed CSV generators
# ---------------------------------------------------------------------------

def _process_oi(raw_records: List[dict], symbol: str, source: str) -> pd.DataFrame:
    rows = []
    for r in raw_records:
        dt = datetime.utcfromtimestamp(r["time"] / 1000)
        rows.append({"time": r["time"], "datetime_utc": dt.isoformat(), "symbol": symbol,
                     "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
                     "source_endpoint": source})
    return pd.DataFrame(rows)


def _process_funding(raw_records: List[dict], symbol: str, source: str) -> pd.DataFrame:
    rows = []
    for r in raw_records:
        dt = datetime.utcfromtimestamp(r["time"] / 1000)
        rows.append({"time": r["time"], "datetime_utc": dt.isoformat(), "symbol": symbol,
                     "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
                     "source_endpoint": source})
    return pd.DataFrame(rows)


def _process_taker(raw_records: List[dict], symbol: str, source: str) -> pd.DataFrame:
    rows = []
    for r in raw_records:
        dt = datetime.utcfromtimestamp(r["time"] / 1000)
        buy = r["aggregated_buy_volume_usd"]
        sell = r["aggregated_sell_volume_usd"]
        denom = buy + sell
        imbalance = (buy - sell) / denom if denom > 0 else 0.0
        rows.append({"time": r["time"], "datetime_utc": dt.isoformat(), "symbol": symbol,
                     "aggregated_buy_volume_usd": buy, "aggregated_sell_volume_usd": sell,
                     "taker_imbalance": round(imbalance, 6), "source_endpoint": source})
    return pd.DataFrame(rows)


def _process_etf(raw_records: List[dict], symbol: str, source: str) -> pd.DataFrame:
    rows = []
    for r in raw_records:
        dt = datetime.utcfromtimestamp(r["timestamp"] / 1000)
        rows.append({"timestamp": r["timestamp"], "datetime_utc": dt.isoformat(), "symbol": symbol,
                     "flow_usd": r["flow_usd"], "price_usd": r.get("price_usd", 0),
                     "source_endpoint": source})
    return pd.DataFrame(rows)


def _process_calendar(raw_records: List[dict], symbol: str = "", source: str = "") -> pd.DataFrame:
    rows = []
    for r in raw_records:
        dt = datetime.utcfromtimestamp(r["publish_timestamp"])
        rows.append({"publish_timestamp": r["publish_timestamp"], "datetime_utc": dt.isoformat(),
                     "calendar_name": r.get("calendar_name", ""),
                     "country_code": r.get("country_code", ""),
                     "country_name": r.get("country_name", ""),
                     "data_effect": r.get("data_effect", ""),
                     "importance_level": r.get("importance_level", 0),
                     "has_exact_publish_time": r.get("has_exact_publish_time", 0),
                     "source_endpoint": source})
    return pd.DataFrame(rows)


PROCESSORS = {
    "open_interest_aggregated": _process_oi,
    "funding_oi_weight": _process_funding,
    "taker_buy_sell_aggregated": _process_taker,
    "bitcoin_etf_flow": _process_etf,
    "ethereum_etf_flow": _process_etf,
    "financial_calendar": _process_calendar,
}


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------

def _build_audit_report(mode: str, api_key_found: bool, results: List[Dict], errors: List[Dict],
                        rate_limit_info: Dict, config: CoinGlassClientConfig) -> str:
    lines = []
    def h(lvl, text): lines.append(f"{'#' * lvl} {text}")

    h(1, "CoinGlass Fetch Audit Report")
    lines.append(f"**生成时间：** {datetime.utcnow().isoformat()} UTC")
    lines.append(f"**执行模式：** {mode}")
    lines.append(f"**API Key 读取：** {'yes' if api_key_found else 'no'}")
    lines.append(f"**allow_network：** {config.fetch.allow_network}")
    lines.append("")

    h(2, "Endpoint 列表")
    for ep in ENDPOINT_DEFS:
        enabled = _endpoint_enabled(ep, config)
        syms = config.symbols if ep.get("per_symbol", False) else [ep.get("symbol_override", "N/A")]
        params = ep["params_fn"](config)
        status = "enabled" if enabled else "disabled"
        lines.append(f"- **{ep['key']}** ({status}): `{ep['path']}` → symbols={syms}, params={params}")
    lines.append("")

    h(2, "Raw JSON 文件")
    for r in results:
        if r.get("raw_path"):
            lines.append(f"- `{r['raw_path']}` ({r.get('record_count', '?')} records)")
    lines.append("")

    h(2, "Processed CSV 文件")
    for r in results:
        if r.get("processed_path"):
            lines.append(f"- `{r['processed_path']}` ({r.get('processed_rows', 0)} rows)")
    lines.append("")

    if errors:
        h(2, "失败 / 错误")
        for e in errors:
            lines.append(f"- **{e['endpoint']}** ({e.get('symbol', 'N/A')}): {e['error']}")
        lines.append("")

    if rate_limit_info:
        h(2, "Rate Limit 信息")
        for k, v in rate_limit_info.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    h(2, "重要声明")
    lines.append("- ⚠️ 本次 **未修改** 交易 CSV（cleaned_trades.csv）")
    lines.append("- ⚠️ 本次 **未修改** 评分 pipeline（main.py）")
    lines.append("- ⚠️ 本次 **未修改** Enable Score、Monte Carlo、Performance Matrix")
    lines.append("- ⚠️ API key **未写入** 本报告")
    if mode in ("dry_run", "mock"):
        lines.append("- ⚠️ 本报告基于 **mock/synthetic 数据**，不反映真实 CoinGlass API 响应")
    lines.append("")

    lines.append("*Generated by Strategy Enable Score System v1.1 — P2-7 CoinGlass Fetch*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_dry_run(config: CoinGlassClientConfig):
    """Print planned endpoints and paths without any writes."""
    logger.info("=== DRY RUN — 计划抓取的 endpoints ===")
    for ep in ENDPOINT_DEFS:
        if not _endpoint_enabled(ep, config):
            logger.info("  [SKIP] %s (disabled)", ep["key"])
            continue
        syms = config.symbols if ep.get("per_symbol", False) else [ep.get("symbol_override", "N/A")]
        for sym in syms:
            raw = _raw_path(config, ep, sym)
            proc = _processed_path(config, ep, sym)
            params = ep["params_fn"](config)
            if ep.get("per_symbol"):
                params = dict(params, symbol=sym)
            logger.info("  %s | symbol=%s | %s", ep["key"], sym, ep["path"])
            logger.info("       params=%s", params)
            logger.info("       raw: %s", raw)
            logger.info("       processed: %s", proc)


def run_mock(config: CoinGlassClientConfig):
    """Generate synthetic raw JSON + processed CSV + audit report."""
    os.makedirs(os.path.join(config.cache_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(config.cache_dir, "processed"), exist_ok=True)
    os.makedirs(config.output_dir, exist_ok=True)

    results = []
    errors = []

    for ep in ENDPOINT_DEFS:
        if not _endpoint_enabled(ep, config):
            continue

        gen_fn = MOCK_GENERATORS.get(ep["key"])
        proc_fn = PROCESSORS.get(ep["key"])
        if not gen_fn or not proc_fn:
            errors.append({"endpoint": ep["key"], "error": "No mock generator"})
            continue

        syms = config.symbols if ep.get("per_symbol", False) else [ep.get("symbol_override", "UNKNOWN")]

        for sym in syms:
            try:
                # Generate mock raw data
                raw_records = gen_fn(sym)
                raw_path = _raw_path(config, ep, sym)

                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump({"code": "0", "data": raw_records}, f, default=str)

                # Generate processed CSV
                df = proc_fn(raw_records, sym, ep["key"])
                processed_path = _processed_path(config, ep, sym)
                df.to_csv(processed_path, index=False)

                results.append({
                    "endpoint": ep["key"], "symbol": sym,
                    "raw_path": raw_path, "record_count": len(raw_records),
                    "processed_path": processed_path, "processed_rows": len(df),
                })
                logger.info("  ✓ %s / %s: %d raw, %d processed", ep["key"], sym, len(raw_records), len(df))
            except Exception as e:
                errors.append({"endpoint": ep["key"], "symbol": sym, "error": str(e)})
                logger.error("  ✗ %s / %s: %s", ep["key"], sym, e)

    # Audit report
    report = _build_audit_report("mock", False, results, errors, {}, config)
    report_path = os.path.join(config.output_dir, "fetch_audit_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Audit report: %s", report_path)


def run_live(config: CoinGlassClientConfig):
    """Fetch real data from CoinGlass API."""
    if not config.fetch.allow_network:
        raise RuntimeError(
            "Live mode requires coinglass.fetch.allow_network=true in config.yaml"
        )

    client = CoinGlassClient(config, allow_network=True)
    if not client.has_api_key():
        raise RuntimeError(
            f"API key not found. Set environment variable {config.api_key_env}."
        )

    os.makedirs(os.path.join(config.cache_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(config.cache_dir, "processed"), exist_ok=True)
    os.makedirs(config.output_dir, exist_ok=True)

    results = []
    errors = []
    proc_fn_map = PROCESSORS

    for ep in ENDPOINT_DEFS:
        if not _endpoint_enabled(ep, config):
            continue

        syms = config.symbols if ep.get("per_symbol", False) else [ep.get("symbol_override", "UNKNOWN")]

        for sym in syms:
            try:
                params = ep["params_fn"](config)
                if ep.get("per_symbol"):
                    params = dict(params, symbol=sym)
                # Handle exchange_list as comma-separated string
                if ep.get("exchange_list") and "exchange_list" in params:
                    params["exchange_list"] = ",".join(params["exchange_list"])

                data = client.get(ep["path"], params=params)
                raw_records = data.get("data", [])

                # Save raw
                raw_path = _raw_path(config, ep, sym)
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, default=str)

                # Process
                proc_fn = proc_fn_map.get(ep["key"])
                if proc_fn and raw_records:
                    df = proc_fn(raw_records, sym, ep["key"])
                    processed_path = _processed_path(config, ep, sym)
                    df.to_csv(processed_path, index=False)
                    processed_rows = len(df)
                else:
                    processed_path = ""
                    processed_rows = 0

                results.append({
                    "endpoint": ep["key"], "symbol": sym,
                    "raw_path": raw_path, "record_count": len(raw_records),
                    "processed_path": processed_path, "processed_rows": processed_rows,
                })
                logger.info("  ✓ %s / %s: %d records", ep["key"], sym, len(raw_records))
            except Exception as e:
                errors.append({"endpoint": ep["key"], "symbol": sym, "error": str(e)})
                logger.error("  ✗ %s / %s: %s", ep["key"], sym, e)

    client.close()
    api_key_found = client.has_api_key()
    rate_info = client.get_rate_limit_info()

    report = _build_audit_report("live", api_key_found, results, errors, rate_info, config)
    report_path = os.path.join(config.output_dir, "fetch_audit_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Audit report: %s", report_path)


def main():
    parser = argparse.ArgumentParser(
        description="Strategy Enable Score System v1.1 — CoinGlass Fetch"
    )
    parser.add_argument("--config", "-c", default="config.yaml", help="Config file path")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without fetching")
    parser.add_argument("--mock", action="store_true", help="Generate synthetic data (no network)")
    parser.add_argument("--live", action="store_true", help="Fetch real data from CoinGlass API")
    parser.add_argument("--symbols", default=None,
                        help="Comma-separated symbols override (e.g. BTC,ETH)")
    parser.add_argument("--endpoints", default=None,
                        help="Comma-separated endpoint keys override (e.g. open_interest_aggregated,funding_oi_weight)")
    parser.add_argument("--output-suffix", default=None,
                        help="Suffix appended to output file names (e.g. live_small_batch)")

    args = parser.parse_args()

    # Exactly one mode must be selected
    modes = [bool(args.dry_run), bool(args.mock), bool(args.live)]
    if sum(modes) != 1:
        parser.error("Exactly one of --dry-run, --mock, --live must be specified")

    full_config = load_config(args.config)
    cg_config = full_config.coinglass

    # Apply CLI overrides (minimal intrusion, only what's explicitly provided)
    if args.symbols is not None:
        cg_config.symbols = [s.strip() for s in args.symbols.split(",")]
        logger.info("CLI override symbols: %s", cg_config.symbols)
    if args.endpoints is not None:
        cg_config.fetcher_endpoints = [s.strip() for s in args.endpoints.split(",")]
        logger.info("CLI override endpoints: %s", cg_config.fetcher_endpoints)
    if args.output_suffix is not None:
        cg_config.output_suffix = args.output_suffix
        logger.info("CLI override output_suffix: %s", cg_config.output_suffix)

    if args.dry_run:
        run_dry_run(cg_config)
    elif args.mock:
        logger.info("=== MOCK MODE — generating synthetic data ===")
        run_mock(cg_config)
    elif args.live:
        logger.info("=== LIVE MODE — fetching from CoinGlass API ===")
        run_live(cg_config)


if __name__ == "__main__":
    main()
