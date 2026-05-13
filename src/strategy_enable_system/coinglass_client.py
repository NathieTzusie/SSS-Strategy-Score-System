"""
CoinGlass API HTTP Client for Strategy Enable Score System v1.1 (P2-7).

Handles:
- Authentication via CG-API-KEY header (from env var, never logged)
- Retry with exponential backoff
- Rate limit tracking
- Timeout handling
- Error response detection (code != "0")
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any

import requests

from .config import CoinGlassClientConfig

logger = logging.getLogger(__name__)


class CoinGlassClient:
    """HTTP client for CoinGlass API v4."""

    def __init__(self, config: CoinGlassClientConfig, allow_network: bool = False):
        self.config = config
        self.allow_network = allow_network
        self._api_key: Optional[str] = None
        self._session = requests.Session()
        self._request_count = 0
        self._last_request_time = 0.0
        self._rate_limit_info: Dict[str, Any] = {}

    def get_api_key(self) -> Optional[str]:
        """Read API key from environment variable. Never logs the key value."""
        if self._api_key is not None:
            return self._api_key if self._api_key else None
        key = os.environ.get(self.config.api_key_env, "")
        self._api_key = key if key else None
        if key:
            logger.info("API key found: %s (not displayed)", self.config.api_key_env)
        else:
            logger.warning("API key not found: %s", self.config.api_key_env)
        return self._api_key

    def has_api_key(self) -> bool:
        return self.get_api_key() is not None

    def can_live(self) -> bool:
        """Check if live mode is allowed."""
        if not self.allow_network:
            return False
        if not self.has_api_key():
            return False
        return True

    def _rate_limit_wait(self):
        """Enforce rate limit between requests."""
        if self._request_count == 0:
            return
        min_interval = 60.0 / self.config.rate_limit_per_minute
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            sleep_s = min_interval - elapsed
            logger.debug("Rate limit: sleeping %.1fs", sleep_s)
            time.sleep(sleep_s)

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.config.user_agent,
            "Content-Type": "application/json",
        }
        api_key = self.get_api_key()
        if api_key:
            headers["CG-API-KEY"] = api_key
        return headers

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GET request to CoinGlass API with retry and rate limiting.
        
        Args:
            path: API path (e.g., '/api/futures/open-interest/aggregated-history').
            params: Query parameters.
        
        Returns:
            Parsed JSON response dict.
        
        Raises:
            RuntimeError: If live mode is not allowed or all retries fail.
            ValueError: If API returns error code != "0".
        """
        if not self.can_live():
            raise RuntimeError(
                "Live mode not allowed. Set coinglass.fetch.allow_network=true "
                "and ensure COINGLASS_API_KEY is set."
            )

        url = self.config.base_url.rstrip("/") + path
        headers = self._build_headers()
        # Sanitize headers for logging (mask API key)
        log_headers = {k: (v[:8] + "..." if k == "CG-API-KEY" else v) for k, v in headers.items()}

        last_error = None
        for attempt in range(self.config.retry_count + 1):
            try:
                self._rate_limit_wait()
                logger.info("GET %s (attempt %d/%d)", url, attempt + 1, self.config.retry_count + 1)
                
                resp = self._session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.config.request_timeout_seconds,
                )
                self._request_count += 1
                self._last_request_time = time.time()

                # Capture rate limit headers
                for hdr in ["API-KEY-MAX-LIMIT", "API-KEY-USE-LIMIT"]:
                    if hdr in resp.headers:
                        self._rate_limit_info[hdr] = resp.headers[hdr]

                resp.raise_for_status()
                data = resp.json()

                # CoinGlass error code check
                code = data.get("code")
                if code is not None and str(code) != "0":
                    msg = data.get("msg", "Unknown API error")
                    raise ValueError(f"CoinGlass API error: code={code}, msg={msg}")

                return data

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning("Request timeout (attempt %d): %s", attempt + 1, e)
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning("Request failed (attempt %d): %s", attempt + 1, e)
            except ValueError as e:
                # API error — don't retry
                raise

            if attempt < self.config.retry_count:
                backoff = self.config.retry_backoff_seconds * (2 ** attempt)
                logger.info("Retrying in %.1fs...", backoff)
                time.sleep(backoff)

        raise RuntimeError(f"All {self.config.retry_count + 1} attempts failed for {url}: {last_error}")

    def get_rate_limit_info(self) -> Dict[str, Any]:
        return dict(self._rate_limit_info)

    def close(self):
        self._session.close()
