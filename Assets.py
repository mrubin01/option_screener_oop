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

    @property
    def symbol(self):
        return self._symbol

    @symbol.setter
    def symbol(self, new_symbol: str):
        if isinstance(new_symbol, str):
            self._symbol = new_symbol
        else:
            print("Invalid symbol! It must be a string")


class Equity(Asset):
    # override constructor
    def __init__(self, symbol, exchange="Unknown"):
        super(Equity, self).__init__(symbol)

        self.exchange = exchange

    def __str__(self):
        return f"{self.symbol} is an equity, its exchange is {self.exchange}"

    @property
    def exchange(self):
        return self._exchange

    @exchange.setter
    def exchange(self, new_exchange: str):
        if isinstance(new_exchange, str):
            self._exchange = new_exchange
        else:
            print("Invalid exchange! It must be a string")

    def get_info(self):
        """ Call Yahoo Finance API and store data into a dict
            If info is empty, call the api with no user-agent """
        beta = "N/A"

        try:
            stock = yf.Ticker(self._symbol)  # session=session)
            info = stock.info

            price = float(info["currentPrice"])
            options = stock.options
            sector = info["sector"]
            industry = info["industry"]
            vol_aver_10days = info["averageDailyVolume10Day"]
            vol_aver_3months = info["averageDailyVolume3Month"]

            try:
                beta = info["beta"]
            except Exception as e:
                pass

        except Exception as e:
            return {}, None, {}, None, None, None, None, None

        return stock, price, options, sector, industry, beta, vol_aver_10days, vol_aver_3months


