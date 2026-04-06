"""Compute live RSI-14, MACD signal-diff, and Bollinger %B from Finnhub candles.

No external technical-analysis library is required — all calculations are pure
pandas arithmetic applied to the last 60 daily OHLCV candles fetched from the
Finnhub /stock/candle endpoint.

Usage
-----
indicators = FinnhubLiveIndicators(api_key=settings.finnhub_api_key)
result = await indicators.fetch("AAPL")
# {"rsi_14": 0.62, "macd_signal_diff": 0.003, "bb_pct_b": 0.78}
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

_CANDLE_URL = "https://finnhub.io/api/v1/stock/candle"
_LOOKBACK_DAYS = 60  # enough for RSI(14), MACD(12,26,9) + Bollinger(20)


class FinnhubLiveIndicators:
    """Fetch recent daily candles from Finnhub and return normalised indicators.

    All returned values are in [0, 1] (or close to it) so they can be fed
    directly into the ML model's ``to_array()`` vector without further scaling.

    Parameters
    ----------
    api_key:
        Finnhub API key.  Read from ``FINNHUB_API_KEY`` env-var by default.
    timeout:
        HTTP timeout in seconds for the Finnhub request.
    """

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        # Accept a single key or discover all configured keys for rotation
        if api_key:
            self._keys = [api_key]
        else:
            try:
                from app.core.config import get_settings
                s = get_settings()
                self._keys = [k for k in [s.finnhub_api_key, s.finnhub_api_key_2] if k]
            except Exception:
                import os
                self._keys = [k for k in [
                    os.environ.get("FINNHUB_API_KEY", ""),
                    os.environ.get("FINNHUB_API_KEY_2", ""),
                ] if k]
        if not self._keys:
            self._keys = [""]
        self._key_idx = 0
        self._timeout = timeout

    def _next_key(self) -> str:
        """Round-robin through available API keys."""
        key = self._keys[self._key_idx % len(self._keys)]
        self._key_idx += 1
        return key

    @property
    def _api_key(self) -> str:
        """Backwards-compatible single-key property."""
        return self._keys[0]

    # ── public API ───────────────────────────────────────────────────────────

    async def fetch(self, symbol: str) -> dict[str, float]:
        """Return live technical indicators for *symbol*.

        Returns
        -------
        dict with keys: ``rsi_14``, ``macd_signal_diff``, ``bb_pct_b``.
        Falls back to neutral values (0.5, 0.0, 0.5) and logs a warning if the
        Finnhub request fails — the pipeline continues and the model uses the
        less-informative default rather than crashing.
        """
        try:
            candles = await self._fetch_candles(symbol)
            close = pd.Series(candles, dtype=float)
            return {
                "rsi_14":          float(self._rsi(close).iloc[-1]),
                "macd_signal_diff": float(self._macd_diff(close).iloc[-1]),
                "bb_pct_b":        float(self._bb_pct_b(close).iloc[-1]),
            }
        except Exception as exc:
            logger.warning(
                "live_indicators_fetch_failed",
                symbol=symbol,
                error=str(exc),
            )
            return {"rsi_14": 0.5, "macd_signal_diff": 0.0, "bb_pct_b": 0.5}

    # ── Finnhub candle fetch ──────────────────────────────────────────────────

    async def _fetch_candles(self, symbol: str) -> list[float]:
        """Fetch the last _LOOKBACK_DAYS daily close prices from Finnhub."""
        now   = int(time.time())
        start = now - _LOOKBACK_DAYS * 86_400  # seconds per day

        params: dict[str, Any] = {
            "symbol":     symbol,
            "resolution": "D",   # daily
            "from":       start,
            "to":         now,
            "token":      self._next_key(),   # round-robin across all keys
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_CANDLE_URL, params=params)
            resp.raise_for_status()

        data = resp.json()
        if data.get("s") != "ok":
            raise ValueError(
                f"Finnhub candle response status '{data.get('s')}' for {symbol}"
            )

        closes: list[float] = data.get("c", [])
        if len(closes) < 30:
            raise ValueError(
                f"Insufficient candle data for {symbol}: got {len(closes)} bars"
            )

        logger.debug("finnhub_candles_fetched", symbol=symbol, bars=len(closes))
        return closes

    # ── Pure-pandas indicator helpers ────────────────────────────────────────

    @staticmethod
    def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """Compute RSI(period) normalised to [0, 1]."""
        delta = close.diff()
        gain  = delta.clip(lower=0.0).rolling(period).mean()
        loss  = (-delta.clip(upper=0.0)).rolling(period).mean()
        rs    = gain / (loss + 1e-9)
        return (rs / (1.0 + rs)).clip(0.0, 1.0)

    @staticmethod
    def _macd_diff(
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> pd.Series:
        """Return (MACD line − signal line) normalised to approx [−1, 1].

        Normalisation: divide by closing price to make scale-invariant, then
        clip to the ±1% band and rescale so 1% maps to ±1.
        """
        ema_fast    = close.ewm(span=fast,   adjust=False).mean()
        ema_slow    = close.ewm(span=slow,   adjust=False).mean()
        macd_line   = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        diff        = (macd_line - signal_line) / (close + 1e-9)
        return (diff.clip(-0.01, 0.01) / 0.01)  # [-1, 1]

    @staticmethod
    def _bb_pct_b(close: pd.Series, period: int = 20, n_std: float = 2.0) -> pd.Series:
        """Compute Bollinger %B(period, n_std) clipped to [0, 1].

        0 = price at or below lower band, 1 = at or above upper band.
        0.5 = price at middle band (SMA).
        """
        sma   = close.rolling(period).mean()
        std   = close.rolling(period).std()
        upper = sma + n_std * std
        lower = sma - n_std * std
        return ((close - lower) / (upper - lower + 1e-9)).clip(0.0, 1.0)
