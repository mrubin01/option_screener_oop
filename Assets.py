import yfinance as yf
from datetime import datetime
import requests_cache
import requests
import pandas as pd


class Asset(object):
    # constructor
    def __init__(self, symbol: str):
        self.symbol = symbol

    def __str__(self):
        return f"{self.symbol} is an asset"


