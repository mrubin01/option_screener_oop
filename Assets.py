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




