import os
from dotenv import load_dotenv
from alpaca.data import StockHistoricalDataClient, OptionHistoricalDataClient

load_dotenv()

_api_key = os.getenv("ALPACA_API_KEY")
_secret_key = os.getenv("ALPACA_SECRET_KEY")

if not _api_key or not _secret_key:
    raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")

stock_client = StockHistoricalDataClient(_api_key, _secret_key)
option_client = OptionHistoricalDataClient(_api_key, _secret_key)

if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
