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


def get_latest_trades(req):
    _limiter.acquire()
    return stock_client.get_latest_stock_trades(req)


def get_stock_bars(req):
    _limiter.acquire()
    return stock_client.get_stock_bars(req)


def get_option_chain(req):
    _limiter.acquire()
    return option_client.get_option_chain(req)


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
