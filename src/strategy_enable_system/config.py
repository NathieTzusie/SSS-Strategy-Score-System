"""
Config Loader for Strategy Enable Score System v1.1.
Reads and validates config.yaml, returns a typed configuration dictionary.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MonteCarloConfig:
    iterations: int = 5000
    method: str = "bootstrap"
    drawdown_threshold_R: float = 10.0
    random_seed: int = 42


@dataclass
class EdgeConcentrationConfig:
    enabled: bool = True
    largest_win_warning_threshold: float = 0.35
    top_5_warning_threshold: float = 0.60
    top_10_percent_warning_threshold: float = 0.70


@dataclass
class ScoreWeights:
    regime_edge: float = 0.40
    recent_health: float = 0.15
    monte_carlo_stability: float = 0.25
    risk_control: float = 0.20


@dataclass
class ScoreThresholds:
    strong_enable: float = 80.0
    medium_enable: float = 65.0
    weak_enable: float = 50.0


@dataclass
class MetricCaps:
    max_profit_factor: float = 10.0
    max_payoff_ratio: float = 10.0


@dataclass
class MarketOpportunityConfig:
    enabled: bool = False
    default_score: float = 1.0


@dataclass
class ReviewRules:
    losing_streak_review_threshold: int = 4
    mc_drawdown_probability_review_threshold: float = 0.25
    low_sample_requires_review: bool = True
    edge_concentration_requires_review: bool = True


@dataclass
class FiltersConfig:
    symbol: List[str] = field(default_factory=list)
    strategy_name: List[str] = field(default_factory=list)
    date_start: Optional[str] = None
    date_end: Optional[str] = None


@dataclass
class ValidationConfig:
    duplicate_trade_id: str = "warning"
    require_exit_after_entry: bool = True
    fill_missing_state_with: str = "unknown"


@dataclass
class RegimeSchemaConfig:
    use_layered_regime_fields: bool = True
    fill_missing_layered_fields_with: str = "unknown"


@dataclass
class SessionBackfillConfig:
    enabled: bool = True
    overwrite_existing: bool = False
    timezone: str = "UTC"
    rules: dict = field(default_factory=lambda: {
        "Asia": [0, 9],
        "London": [7, 16],
        "NY": [12, 21],
        "overlap": [12, 16],
    })


@dataclass
class StructureStateBackfillConfig:
    enabled: bool = True
    overwrite_existing: bool = False
    source_field: str = "regime"


@dataclass
class RegimeSnapshotNormalizationConfig:
    enabled: bool = True
    overwrite_existing: bool = False
    preserve_original_column: str = "original_regime_snapshot_id"
    format: str = "{regime}_{YYYYMMDD}"


@dataclass
class ReadinessConfig:
    unknown_warning_threshold: float = 0.20
    unknown_blocking_threshold: float = 0.50
    snapshot_unique_ratio_too_high: float = 0.70
    snapshot_unique_ratio_too_low: float = 0.05
    snapshot_min_avg_trades_per_snapshot: float = 2.0


@dataclass
class LabelQualityConfig:
    enabled: bool = False
    output_dir: str = "outputs/data_quality"
    cleaned_csv_name: str = "cleaned_trades.csv"
    preserve_original_regime_snapshot_id: bool = True
    session_backfill: SessionBackfillConfig = field(default_factory=SessionBackfillConfig)
    structure_state_backfill: StructureStateBackfillConfig = field(default_factory=StructureStateBackfillConfig)
    regime_snapshot_normalization: RegimeSnapshotNormalizationConfig = field(default_factory=RegimeSnapshotNormalizationConfig)
    readiness: ReadinessConfig = field(default_factory=ReadinessConfig)


@dataclass
class CoinGlassFuturesConfig:
    exchanges: List[str] = field(default_factory=lambda: ["Binance"])
    exchange_list: List[str] = field(default_factory=lambda: ["Binance", "OKX", "Bybit"])
    interval: str = "1d"
    intraday_interval: str = "1h"
    limit: int = 1000
    endpoints: dict = field(default_factory=lambda: {
        "open_interest_aggregated": True,
        "funding_oi_weight": True,
        "taker_buy_sell_aggregated": True,
    })


@dataclass
class CoinGlassETFConfig:
    endpoints: dict = field(default_factory=lambda: {
        "bitcoin_flow_history": True,
        "ethereum_flow_history": True,
    })


@dataclass
class CoinGlassCalendarConfig:
    enabled: bool = True
    language: str = "en"
    lookback_days: int = 15
    lookahead_days: int = 15


@dataclass
class CoinGlassFetchConfig:
    mode: str = "dry_run"
    allow_network: bool = False
    overwrite_raw_cache: bool = False
    overwrite_processed: bool = True


@dataclass
class CoinGlassClientConfig:
    enabled: bool = False
    api_key_env: str = "COINGLASS_API_KEY"
    base_url: str = "https://open-api-v4.coinglass.com"
    cache_dir: str = "data/external/coinglass"
    output_dir: str = "outputs/coinglass"
    user_agent: str = "strategy-enable-system/1.1"
    rate_limit_per_minute: int = 30
    request_timeout_seconds: int = 30
    retry_count: int = 2
    retry_backoff_seconds: float = 2.0
    symbols: List[str] = field(default_factory=lambda: ["BTC", "ETH"])
    fetcher_endpoints: Optional[List[str]] = None  # CLI override: only fetch these endpoints
    output_suffix: str = ""  # CLI override: appended to output paths
    futures: CoinGlassFuturesConfig = field(default_factory=CoinGlassFuturesConfig)
    etf: CoinGlassETFConfig = field(default_factory=CoinGlassETFConfig)
    calendar: CoinGlassCalendarConfig = field(default_factory=CoinGlassCalendarConfig)
    fetch: CoinGlassFetchConfig = field(default_factory=CoinGlassFetchConfig)


@dataclass
class EnrichmentAlignmentConfig:
    time_field: str = "entry_time"
    prevent_lookahead: bool = True
    futures_interval: str = "1h"
    daily_interval: str = "1d"
    max_staleness_hours: dict = field(default_factory=lambda: {"futures": 48, "etf": 96, "calendar": 48})


@dataclass
class EnrichmentThresholdsConfig:
    oi_change_pct_rising: float = 0.03
    oi_change_pct_falling: float = -0.03
    funding_positive: float = 0.0001
    funding_negative: float = -0.0001
    taker_imbalance_bullish: float = 0.10
    taker_imbalance_bearish: float = -0.10
    etf_flow_inflow_usd: float = 50_000_000
    etf_flow_outflow_usd: float = -50_000_000
    macro_event_window_hours: int = 12
    macro_high_importance_level: int = 3


@dataclass
class EnrichmentFieldsConfig:
    enrich_oi_state: bool = True
    enrich_funding_state: bool = True
    enrich_orderflow_state: bool = True
    enrich_etf_flow_state: bool = True
    enrich_macro_state: bool = True


@dataclass
class LabelEnrichmentConfig:
    enabled: bool = False
    input_path: str = "outputs/data_quality/cleaned_trades.csv"
    output_path: str = "outputs/data_quality/enriched_trades.csv"
    audit_report_path: str = "outputs/data_quality/enrichment_audit_report.md"
    processed_dir: str = "data/external/coinglass/processed"
    preserve_original_columns: bool = True
    alignment: EnrichmentAlignmentConfig = field(default_factory=EnrichmentAlignmentConfig)
    thresholds: EnrichmentThresholdsConfig = field(default_factory=EnrichmentThresholdsConfig)
    fields: EnrichmentFieldsConfig = field(default_factory=EnrichmentFieldsConfig)


@dataclass
class PartialContextConfig:
    """P2-14: Partial Context Report configuration."""
    enabled: bool = False
    input_path: str = "outputs/data_quality/enriched_trades_full_year.csv"
    quality_summary_path: str = "outputs/data_quality_full_year/label_quality_summary.csv"
    output_dir: str = "outputs/context"
    summary_csv_name: str = "partial_context_summary.csv"
    report_name: str = "partial_context_report.md"
    mode: str = "partial_context_mode"
    informational_only: bool = True
    group_by: List[str] = field(default_factory=lambda: ["strategy_name", "regime"])
    fields: List[str] = field(default_factory=lambda: [
        "session", "structure_state", "volatility_state",
        "oi_state", "funding_state", "etf_flow_state",
    ])
    excluded_fields: List[str] = field(default_factory=lambda: [
        "orderflow_state", "macro_state", "coinbase_premium_state",
    ])
    min_coverage_for_field: float = 0.80
    top_n_values: int = 5


@dataclass
class MonitorInputsConfig:
    """P2-15: Data Quality Monitor input paths."""
    label_quality_summary: str = "outputs/data_quality_full_year/label_quality_summary.csv"
    enrichment_audit_report: str = "outputs/data_quality/enrichment_audit_report_full_year.md"
    coinglass_fetch_report: str = "outputs/coinglass_live_full/full_year_fetch_report.md"
    partial_context_summary: str = "outputs/context/partial_context_summary.csv"
    official_baseline_dir: str = "outputs/baseline_cleaned_official"
    current_default_outputs_dir: str = "outputs"


@dataclass
class MonitorThresholdsConfig:
    """P2-15: Monitor thresholds."""
    pass_coverage: float = 0.80
    warn_coverage: float = 0.50
    max_allowed_enable_score_delta: float = 0.000001
    require_context_fields_pass: List[str] = field(default_factory=lambda: [
        "session", "structure_state", "volatility_state",
        "oi_state", "funding_state", "etf_flow_state",
    ])


@dataclass
class FeatureGatesConfig:
    """P2-15: Feature gate requirements."""
    classifier_requires: dict = field(default_factory=lambda: {
        "orderflow_state_coverage": 0.80,
        "macro_true_event_coverage": 0.80,
    })
    market_opportunity_requires: dict = field(default_factory=lambda: {
        "orderflow_state_coverage": 0.80,
        "macro_true_event_coverage": 0.80,
        "etf_flow_state_coverage": 0.80,
    })
    partial_context_requires: dict = field(default_factory=lambda: {
        "included_field_coverage": 0.80,
    })


@dataclass
class DataQualityMonitorConfig:
    """P2-15: Data Quality Monitor configuration."""
    enabled: bool = False
    output_dir: str = "outputs/monitor"
    report_name: str = "data_quality_monitor_report.md"
    summary_csv_name: str = "data_quality_monitor_summary.csv"
    inputs: MonitorInputsConfig = field(default_factory=MonitorInputsConfig)
    thresholds: MonitorThresholdsConfig = field(default_factory=MonitorThresholdsConfig)
    feature_gates: FeatureGatesConfig = field(default_factory=FeatureGatesConfig)


@dataclass
class ReportOutputConfig:
    """Controls how report output directories are organized.
    
    run_mode:
      "timestamped" — create {output_dir}/{YYYY-MM-DD}/{run_slug}/ each run
      "legacy"     — write directly to {output_dir}/ (overwrites)
    """
    run_mode: str = "timestamped"
    run_name: Optional[str] = None   # Override auto-generated run_slug
    overwrite: bool = False          # Allow overwriting an existing run dir


@dataclass
class SSSConfig:
    input_path: List[str] = field(default_factory=list)
    output_dir: str = "outputs"
    min_trades: int = 30
    recent_trade_window: int = 20
    report_output: ReportOutputConfig = field(default_factory=ReportOutputConfig)
    monte_carlo: MonteCarloConfig = field(default_factory=MonteCarloConfig)
    market_opportunity: MarketOpportunityConfig = field(default_factory=MarketOpportunityConfig)
    edge_concentration: EdgeConcentrationConfig = field(default_factory=EdgeConcentrationConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    score_thresholds: ScoreThresholds = field(default_factory=ScoreThresholds)
    metric_caps: MetricCaps = field(default_factory=MetricCaps)
    review_rules: ReviewRules = field(default_factory=ReviewRules)
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    regime_schema: RegimeSchemaConfig = field(default_factory=RegimeSchemaConfig)
    label_quality: LabelQualityConfig = field(default_factory=LabelQualityConfig)
    coinglass: CoinGlassClientConfig = field(default_factory=CoinGlassClientConfig)
    label_enrichment: LabelEnrichmentConfig = field(default_factory=LabelEnrichmentConfig)
    partial_context: PartialContextConfig = field(default_factory=PartialContextConfig)
    data_quality_monitor: DataQualityMonitorConfig = field(default_factory=DataQualityMonitorConfig)
    recommendations: "RecommendationsConfig" = field(default_factory=lambda: _default_recommendations())


def _default_recommendations():
    from .recommendations import RecommendationsConfig
    return RecommendationsConfig()


def load_config(config_path: str) -> SSSConfig:
    """Load and validate configuration from YAML file.
    
    Args:
        config_path: Path to config.yaml file.
    
    Returns:
        SSSConfig: Validated configuration object.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If required fields are missing or invalid.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError("Config file is empty.")

    # Validate required top-level fields
    _validate_required_fields(raw)

    config = SSSConfig()

    # Basic fields
    config.input_path = raw.get("input_path", [])
    if not config.input_path:
        raise ValueError("input_path must contain at least one CSV file path.")
    config.output_dir = raw.get("output_dir", "outputs")
    config.min_trades = int(raw.get("min_trades", 30))
    config.recent_trade_window = int(raw.get("recent_trade_window", 20))

    # Subsections
    config.monte_carlo = _parse_monte_carlo(raw.get("monte_carlo", {}))
    config.market_opportunity = _parse_market_opportunity(raw.get("market_opportunity", {}))
    config.edge_concentration = _parse_edge_concentration(raw.get("edge_concentration", {}))
    config.score_weights = _parse_score_weights(raw.get("score_weights", {}))
    config.score_thresholds = _parse_score_thresholds(raw.get("score_thresholds", {}))
    config.metric_caps = _parse_metric_caps(raw.get("metric_caps", {}))
    config.review_rules = _parse_review_rules(raw.get("review_rules", {}))
    config.filters = _parse_filters(raw.get("filters", {}))
    config.validation = _parse_validation(raw.get("validation", {}))
    config.regime_schema = _parse_regime_schema(raw.get("regime_schema", {}))
    config.label_quality = _parse_label_quality(raw.get("label_quality", {}))
    config.coinglass = _parse_coinglass(raw.get("coinglass", {}))
    config.label_enrichment = _parse_label_enrichment(raw.get("label_enrichment", {}))
    config.partial_context = _parse_partial_context(raw.get("partial_context", {}))
    config.data_quality_monitor = _parse_data_quality_monitor(raw.get("data_quality_monitor", {}))
    config.recommendations = _parse_recommendations(raw.get("recommendations", {}))

    # Validate consistency
    _validate_weights(config)
    _validate_thresholds(config)

    return config


def _validate_required_fields(raw: dict):
    """Check for required top-level fields."""
    required = ["input_path"]
    for field in required:
        if field not in raw or not raw[field]:
            raise ValueError(f"Missing required config field: '{field}'")


def _parse_monte_carlo(raw: dict) -> MonteCarloConfig:
    method = raw.get("method", "bootstrap")
    if method not in ("bootstrap", "shuffle"):
        raise ValueError(f"Invalid Monte Carlo method: {method}. Use 'bootstrap' or 'shuffle'.")
    return MonteCarloConfig(
        iterations=int(raw.get("iterations", 5000)),
        method=method,
        drawdown_threshold_R=float(raw.get("drawdown_threshold_R", 10.0)),
        random_seed=int(raw.get("random_seed", 42)),
    )


def _parse_market_opportunity(raw: dict) -> MarketOpportunityConfig:
    return MarketOpportunityConfig(
        enabled=bool(raw.get("enabled", False)),
        default_score=float(raw.get("default_score", 1.0)),
    )


def _parse_edge_concentration(raw: dict) -> EdgeConcentrationConfig:
    return EdgeConcentrationConfig(
        enabled=bool(raw.get("enabled", True)),
        largest_win_warning_threshold=float(raw.get("largest_win_warning_threshold", 0.35)),
        top_5_warning_threshold=float(raw.get("top_5_warning_threshold", 0.60)),
        top_10_percent_warning_threshold=float(raw.get("top_10_percent_warning_threshold", 0.70)),
    )


def _parse_score_weights(raw: dict) -> ScoreWeights:
    weights = ScoreWeights(
        regime_edge=float(raw.get("regime_edge", 0.40)),
        recent_health=float(raw.get("recent_health", 0.15)),
        monte_carlo_stability=float(raw.get("monte_carlo_stability", 0.25)),
        risk_control=float(raw.get("risk_control", 0.20)),
    )
    total = weights.regime_edge + weights.recent_health + weights.monte_carlo_stability + weights.risk_control
    if abs(total - 1.0) > 0.001:
        import warnings
        warnings.warn(f"Score weights sum to {total:.3f}, expected 1.0. Results may be biased.")
    return weights


def _parse_score_thresholds(raw: dict) -> ScoreThresholds:
    thresholds = ScoreThresholds(
        strong_enable=float(raw.get("strong_enable", 80.0)),
        medium_enable=float(raw.get("medium_enable", 65.0)),
        weak_enable=float(raw.get("weak_enable", 50.0)),
    )
    if not (0 < thresholds.weak_enable < thresholds.medium_enable < thresholds.strong_enable <= 100):
        import warnings
        warnings.warn("Score thresholds should satisfy: 0 < weak < medium < strong <= 100")
    return thresholds


def _parse_metric_caps(raw: dict) -> MetricCaps:
    return MetricCaps(
        max_profit_factor=float(raw.get("max_profit_factor", 10.0)),
        max_payoff_ratio=float(raw.get("max_payoff_ratio", 10.0)),
    )


def _parse_review_rules(raw: dict) -> ReviewRules:
    return ReviewRules(
        losing_streak_review_threshold=int(raw.get("losing_streak_review_threshold", 4)),
        mc_drawdown_probability_review_threshold=float(raw.get("mc_drawdown_probability_review_threshold", 0.25)),
        low_sample_requires_review=bool(raw.get("low_sample_requires_review", True)),
        edge_concentration_requires_review=bool(raw.get("edge_concentration_requires_review", True)),
    )


def _parse_filters(raw: dict) -> FiltersConfig:
    return FiltersConfig(
        symbol=raw.get("symbol", []),
        strategy_name=raw.get("strategy_name", []),
        date_start=raw.get("date_start"),
        date_end=raw.get("date_end"),
    )


def _parse_validation(raw: dict) -> ValidationConfig:
    dup_mode = raw.get("duplicate_trade_id", "warning")
    if dup_mode not in ("warning", "error", "ignore"):
        raise ValueError(f"Invalid duplicate_trade_id mode: {dup_mode}. Use 'warning', 'error', or 'ignore'.")
    return ValidationConfig(
        duplicate_trade_id=dup_mode,
        require_exit_after_entry=bool(raw.get("require_exit_after_entry", True)),
        fill_missing_state_with=str(raw.get("fill_missing_state_with", "unknown")),
    )


def _parse_regime_schema(raw: dict) -> RegimeSchemaConfig:
    return RegimeSchemaConfig(
        use_layered_regime_fields=bool(raw.get("use_layered_regime_fields", True)),
        fill_missing_layered_fields_with=str(raw.get("fill_missing_layered_fields_with", "unknown")),
    )


def _validate_weights(config: SSSConfig):
    """None-trivial validation: weights already warned, no error needed."""
    pass


def _validate_thresholds(config: SSSConfig):
    """Validate threshold consistency."""
    t = config.score_thresholds
    if t.weak_enable >= t.medium_enable or t.medium_enable >= t.strong_enable:
        import warnings
        warnings.warn("Threshold hierarchy should be: weak < medium < strong")


def _parse_label_quality(raw: dict) -> LabelQualityConfig:
    """Parse label_quality config section."""
    if not raw:
        return LabelQualityConfig()

    sb_raw = raw.get("session_backfill", {})
    ss_raw = raw.get("structure_state_backfill", {})
    sn_raw = raw.get("regime_snapshot_normalization", {})

    sb = SessionBackfillConfig(
        enabled=bool(sb_raw.get("enabled", True)),
        overwrite_existing=bool(sb_raw.get("overwrite_existing", False)),
        timezone=str(sb_raw.get("timezone", "UTC")),
        rules=sb_raw.get("rules", {"Asia": [0, 8], "London": [8, 13], "NY": [13, 21], "Off": [21, 24]}),
    )

    ss = StructureStateBackfillConfig(
        enabled=bool(ss_raw.get("enabled", True)),
        overwrite_existing=bool(ss_raw.get("overwrite_existing", False)),
        source_field=str(ss_raw.get("source_field", "regime")),
    )

    sn = RegimeSnapshotNormalizationConfig(
        enabled=bool(sn_raw.get("enabled", True)),
        overwrite_existing=bool(sn_raw.get("overwrite_existing", False)),
        preserve_original_column=str(sn_raw.get("preserve_original_column", "original_regime_snapshot_id")),
        format=str(sn_raw.get("format", "{regime}_{YYYYMMDD}")),
    )

    return LabelQualityConfig(
        enabled=bool(raw.get("enabled", False)),
        output_dir=str(raw.get("output_dir", "outputs/data_quality")),
        cleaned_csv_name=str(raw.get("cleaned_csv_name", "cleaned_trades.csv")),
        preserve_original_regime_snapshot_id=bool(raw.get("preserve_original_regime_snapshot_id", True)),
        session_backfill=sb,
        structure_state_backfill=ss,
        regime_snapshot_normalization=sn,
        readiness=_parse_readiness(raw.get("readiness", {})),
    )


def _parse_readiness(raw: dict) -> ReadinessConfig:
    if not raw:
        return ReadinessConfig()
    return ReadinessConfig(
        unknown_warning_threshold=float(raw.get("unknown_warning_threshold", 0.20)),
        unknown_blocking_threshold=float(raw.get("unknown_blocking_threshold", 0.50)),
        snapshot_unique_ratio_too_high=float(raw.get("snapshot_unique_ratio_too_high", 0.70)),
        snapshot_unique_ratio_too_low=float(raw.get("snapshot_unique_ratio_too_low", 0.05)),
        snapshot_min_avg_trades_per_snapshot=float(raw.get("snapshot_min_avg_trades_per_snapshot", 2.0)),
    )


def _parse_coinglass(raw: dict) -> CoinGlassClientConfig:
    if not raw:
        return CoinGlassClientConfig()
    
    futures_raw = raw.get("futures", {})
    etf_raw = raw.get("etf", {})
    cal_raw = raw.get("calendar", {})
    fetch_raw = raw.get("fetch", {})
    
    futures = CoinGlassFuturesConfig(
        exchanges=futures_raw.get("exchanges", ["Binance"]),
        exchange_list=futures_raw.get("exchange_list", ["Binance", "OKX", "Bybit"]),
        interval=str(futures_raw.get("interval", "1d")),
        intraday_interval=str(futures_raw.get("intraday_interval", "1h")),
        limit=int(futures_raw.get("limit", 1000)),
        endpoints=futures_raw.get("endpoints", {}),
    )
    
    etf = CoinGlassETFConfig(
        endpoints=etf_raw.get("endpoints", {}),
    )
    
    cal = CoinGlassCalendarConfig(
        enabled=bool(cal_raw.get("enabled", True)),
        language=str(cal_raw.get("language", "en")),
        lookback_days=int(cal_raw.get("lookback_days", 15)),
        lookahead_days=int(cal_raw.get("lookahead_days", 15)),
    )
    
    fconf = CoinGlassFetchConfig(
        mode=str(fetch_raw.get("mode", "dry_run")),
        allow_network=bool(fetch_raw.get("allow_network", False)),
        overwrite_raw_cache=bool(fetch_raw.get("overwrite_raw_cache", False)),
        overwrite_processed=bool(fetch_raw.get("overwrite_processed", True)),
    )
    
    return CoinGlassClientConfig(
        enabled=bool(raw.get("enabled", False)),
        api_key_env=str(raw.get("api_key_env", "COINGLASS_API_KEY")),
        base_url=str(raw.get("base_url", "https://open-api-v4.coinglass.com")),
        cache_dir=str(raw.get("cache_dir", "data/external/coinglass")),
        output_dir=str(raw.get("output_dir", "outputs/coinglass")),
        user_agent=str(raw.get("user_agent", "strategy-enable-system/1.1")),
        rate_limit_per_minute=int(raw.get("rate_limit_per_minute", 30)),
        request_timeout_seconds=int(raw.get("request_timeout_seconds", 30)),
        retry_count=int(raw.get("retry_count", 2)),
        retry_backoff_seconds=float(raw.get("retry_backoff_seconds", 2.0)),
        symbols=raw.get("symbols", ["BTC", "ETH"]),
        fetcher_endpoints=raw.get("fetcher_endpoints"),
        output_suffix=str(raw.get("output_suffix", "")),
        futures=futures,
        etf=etf,
        calendar=cal,
        fetch=fconf,
    )


def _parse_label_enrichment(raw: dict) -> LabelEnrichmentConfig:
    if not raw:
        return LabelEnrichmentConfig()
    
    align_raw = raw.get("alignment", {})
    thr_raw = raw.get("thresholds", {})
    fld_raw = raw.get("fields", {})
    
    alignment = EnrichmentAlignmentConfig(
        time_field=str(align_raw.get("time_field", "entry_time")),
        prevent_lookahead=bool(align_raw.get("prevent_lookahead", True)),
        futures_interval=str(align_raw.get("futures_interval", "1h")),
        daily_interval=str(align_raw.get("daily_interval", "1d")),
        max_staleness_hours=align_raw.get("max_staleness_hours", {"futures": 48, "etf": 96, "calendar": 48}),
    )
    
    thresholds = EnrichmentThresholdsConfig(
        oi_change_pct_rising=float(thr_raw.get("oi_change_pct_rising", 0.03)),
        oi_change_pct_falling=float(thr_raw.get("oi_change_pct_falling", -0.03)),
        funding_positive=float(thr_raw.get("funding_positive", 0.0001)),
        funding_negative=float(thr_raw.get("funding_negative", -0.0001)),
        taker_imbalance_bullish=float(thr_raw.get("taker_imbalance_bullish", 0.10)),
        taker_imbalance_bearish=float(thr_raw.get("taker_imbalance_bearish", -0.10)),
        etf_flow_inflow_usd=float(thr_raw.get("etf_flow_inflow_usd", 50000000)),
        etf_flow_outflow_usd=float(thr_raw.get("etf_flow_outflow_usd", -50000000)),
        macro_event_window_hours=int(thr_raw.get("macro_event_window_hours", 12)),
        macro_high_importance_level=int(thr_raw.get("macro_high_importance_level", 3)),
    )
    
    fields = EnrichmentFieldsConfig(
        enrich_oi_state=bool(fld_raw.get("enrich_oi_state", True)),
        enrich_funding_state=bool(fld_raw.get("enrich_funding_state", True)),
        enrich_orderflow_state=bool(fld_raw.get("enrich_orderflow_state", True)),
        enrich_etf_flow_state=bool(fld_raw.get("enrich_etf_flow_state", True)),
        enrich_macro_state=bool(fld_raw.get("enrich_macro_state", True)),
    )
    
    return LabelEnrichmentConfig(
        enabled=bool(raw.get("enabled", False)),
        input_path=str(raw.get("input_path", "outputs/data_quality/cleaned_trades.csv")),
        output_path=str(raw.get("output_path", "outputs/data_quality/enriched_trades.csv")),
        audit_report_path=str(raw.get("audit_report_path", "outputs/data_quality/enrichment_audit_report.md")),
        processed_dir=str(raw.get("processed_dir", "data/external/coinglass/processed")),
        preserve_original_columns=bool(raw.get("preserve_original_columns", True)),
        alignment=alignment,
        thresholds=thresholds,
        fields=fields,
    )


def _parse_partial_context(raw: dict) -> PartialContextConfig:
    """Parse partial_context config section (P2-14)."""
    if not raw:
        return PartialContextConfig()
    return PartialContextConfig(
        enabled=bool(raw.get("enabled", False)),
        input_path=str(raw.get("input_path", "outputs/data_quality/enriched_trades_full_year.csv")),
        quality_summary_path=str(raw.get("quality_summary_path", "outputs/data_quality_full_year/label_quality_summary.csv")),
        output_dir=str(raw.get("output_dir", "outputs/context")),
        summary_csv_name=str(raw.get("summary_csv_name", "partial_context_summary.csv")),
        report_name=str(raw.get("report_name", "partial_context_report.md")),
        mode=str(raw.get("mode", "partial_context_mode")),
        informational_only=bool(raw.get("informational_only", True)),
        group_by=raw.get("group_by", ["strategy_name", "regime"]),
        fields=raw.get("fields", PartialContextConfig().fields),
        excluded_fields=raw.get("excluded_fields", PartialContextConfig().excluded_fields),
        min_coverage_for_field=float(raw.get("min_coverage_for_field", 0.80)),
        top_n_values=int(raw.get("top_n_values", 5)),
    )


def _parse_data_quality_monitor(raw: dict) -> DataQualityMonitorConfig:
    """Parse data_quality_monitor config section (P2-15)."""
    if not raw:
        return DataQualityMonitorConfig()
    inp_raw = raw.get("inputs", {})
    thr_raw = raw.get("thresholds", {})
    fg_raw = raw.get("feature_gates", {})
    return DataQualityMonitorConfig(
        enabled=bool(raw.get("enabled", False)),
        output_dir=str(raw.get("output_dir", "outputs/monitor")),
        report_name=str(raw.get("report_name", "data_quality_monitor_report.md")),
        summary_csv_name=str(raw.get("summary_csv_name", "data_quality_monitor_summary.csv")),
        inputs=MonitorInputsConfig(
            label_quality_summary=str(inp_raw.get("label_quality_summary",
                MonitorInputsConfig().label_quality_summary)),
            enrichment_audit_report=str(inp_raw.get("enrichment_audit_report",
                MonitorInputsConfig().enrichment_audit_report)),
            coinglass_fetch_report=str(inp_raw.get("coinglass_fetch_report",
                MonitorInputsConfig().coinglass_fetch_report)),
            partial_context_summary=str(inp_raw.get("partial_context_summary",
                MonitorInputsConfig().partial_context_summary)),
            official_baseline_dir=str(inp_raw.get("official_baseline_dir",
                MonitorInputsConfig().official_baseline_dir)),
            current_default_outputs_dir=str(inp_raw.get("current_default_outputs_dir",
                MonitorInputsConfig().current_default_outputs_dir)),
        ),
        thresholds=MonitorThresholdsConfig(
            pass_coverage=float(thr_raw.get("pass_coverage", 0.80)),
            warn_coverage=float(thr_raw.get("warn_coverage", 0.50)),
            max_allowed_enable_score_delta=float(thr_raw.get("max_allowed_enable_score_delta", 0.000001)),
            require_context_fields_pass=thr_raw.get("require_context_fields_pass",
                MonitorThresholdsConfig().require_context_fields_pass),
        ),
        feature_gates=FeatureGatesConfig(
            classifier_requires=fg_raw.get("classifier_requires",
                FeatureGatesConfig().classifier_requires),
            market_opportunity_requires=fg_raw.get("market_opportunity_requires",
                FeatureGatesConfig().market_opportunity_requires),
            partial_context_requires=fg_raw.get("partial_context_requires",
                FeatureGatesConfig().partial_context_requires),
        ),
    )


def _parse_recommendations(raw: dict) -> "RecommendationsConfig":
    from .recommendations import RecommendationsConfig
    return RecommendationsConfig(
        enabled=bool(raw.get("enabled", True)),
        min_strategy_trade_count=int(raw.get("min_strategy_trade_count", 30)),
        min_group_trade_count=int(raw.get("min_group_trade_count", 15)),
        poor_profit_factor=float(raw.get("poor_profit_factor", 1.0)),
        weak_profit_factor=float(raw.get("weak_profit_factor", 1.2)),
        poor_win_rate=float(raw.get("poor_win_rate", 0.45)),
        weak_win_rate=float(raw.get("weak_win_rate", 0.50)),
        high_drawdown_R=float(raw.get("high_drawdown_R", 5.0)),
        low_payoff_ratio=float(raw.get("low_payoff_ratio", 0.8)),
        high_payoff_ratio=float(raw.get("high_payoff_ratio", 1.5)),
        poor_avg_R=float(raw.get("poor_avg_R", 0.0)),
        high_loss_concentration_R=float(raw.get("high_loss_concentration_R", 0.5)),
        max_recommendations=int(raw.get("max_recommendations", 50)),
    )
