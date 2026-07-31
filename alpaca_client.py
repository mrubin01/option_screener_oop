import os
import time
import threading
from dotenv import load_dotenv
from alpaca.data import StockHistoricalDataClient, OptionHistoricalDataClient

load_dotenv()

_api_key = os.getenv("ALPACA_API_KEY")
_secret_key = os.getenv("ALPACA_SECRET_KEY")

if not _api_key or not _secret_key:
    raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")

stock_client = StockHistoricalDataClient(_api_key, _secret_key)
option_client = OptionHistoricalDataClient(_api_key, _secret_key)


class _RateLimiter:
    """Token-bucket rate limiter. Refills to capacity every 60 seconds."""

    def __init__(self, calls_per_minute: int):
        self._limit = calls_per_minute
        self._tokens = float(calls_per_minute)
        self._lock = threading.Lock()
        self._last_refill = time.monotonic()

    def acquire(self):
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                # Drip tokens in proportion to elapsed time
                self._tokens = min(
                    self._limit,
                    self._tokens + elapsed * (self._limit / 60.0),
                )
                self._last_refill = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
            time.sleep(0.05)


_limiter = _RateLimiter(180)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


def _is_retryable(e: Exception) -> bool:
    msg = str(e).lower()
    return (
        "too many requests" in msg
        or "connection aborted" in msg
        or "remote end closed" in msg
        or "remotedisconnected" in msg
        or "connection reset" in msg
    )


def _call_with_retry(fn, req):
    for attempt in range(_MAX_RETRIES):
        _limiter.acquire()
        try:
            return fn(req)
        except Exception as e:
            if _is_retryable(e) and attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BASE_DELAY * (2 ** attempt))
                continue
            raise


def get_latest_trades(req):
    return _call_with_retry(stock_client.get_stock_latest_trade, req)


def get_stock_bars(req):
    return _call_with_retry(stock_client.get_stock_bars, req)


def get_option_chain(req):
    return _call_with_retry(option_client.get_option_chain, req)



if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
