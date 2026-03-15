import yfinance as yf
from datetime import datetime
import requests_cache
import requests
import pandas as pd
import numpy as np
import functions


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

    def get_info(self) -> dict:
        """ Call yfinance and store data into a dict """
        try:
            stock = yf.Ticker(self._symbol)
            if not stock:
                return {}

            info = stock.info
            if not info or not isinstance(info, dict):
                return {}

            price = info.get("currentPrice")
            if price is None:
                return {}
            price = float(price)

            options = stock.options
            if options is None or len(options) == 0:
                return {}

            return {
                "stock": stock,
                "price": price,
                "options": options,
                "sector": info["sector"],
                "industry": info["industry"],
                "beta": info["beta"],
                "vol_aver_10days": info["averageDailyVolume10Day"],
                "vol_aver_3months": info["averageDailyVolume3Month"],
            }

        except Exception:
            return {}

    def get_price_stats(self) -> dict:
        try:
            data = yf.download(self._symbol, period="3mo", group_by="column", progress=False)

            if data is None or data.empty:
                return {}

            if "Close" not in data:
                return {}

            close_prices = data["Close"]

            # Normalize to a Series for a single ticker
            if hasattr(close_prices, "columns"):
                if self._symbol not in close_prices.columns:
                    return {}
                close_prices = close_prices[self._symbol]

            if close_prices is None or close_prices.empty:
                return {}

            close_prices = close_prices.dropna()
            if close_prices.empty:
                return {}

            low = round(float(close_prices.min()), 2)
            high = round(float(close_prices.max()), 2)
            avg_price = round(float(close_prices.mean()), 2)
            avg_price_7d = round(float(close_prices.tail(7).mean()), 2)
            avg_price_30d = round(float(close_prices.tail(30).mean()), 2)
            last_price = round(float(close_prices.iloc[-1]), 2)
            first_price = round(float(close_prices.iloc[0]), 2)

            price_trend = functions.get_price_trend(close_prices)
            abs_sd, rel_sd = functions.get_std_dev(self._symbol, close_prices)

            return {
                "low": low,
                "high": high,
                "first_price": first_price,
                "last_price": last_price,
                "avg_price": avg_price,
                "avg_price_7d": avg_price_7d,
                "avg_price_30d": avg_price_30d,
                "price_trend": price_trend,
                "abs_sd": abs_sd,
                "rel_sd": rel_sd,
            }

        except Exception as e:
            print(f"Price download failed for {self._symbol}: {e}")
            return {}


class ETF(Asset):
    # override constructor
    def __init__(self, symbol, exchange="Unknown"):
        super(ETF, self).__init__(symbol)

        self.exchange = exchange

    def __str__(self):
        return f"{self.symbol} is an ETF, its exchange is {self.exchange}"

    @property
    def exchange(self):
        return self._exchange

    @exchange.setter
    def exchange(self, new_exchange: str):
        if isinstance(new_exchange, str):
            self._exchange = new_exchange
        else:
            print("Invalid exchange! It must be a string")

    def get_info_etf(self):
        """ Call Yahoo Finance API and store data into a dict """

        try:
            stock = yf.Ticker(self._symbol)  # session=session)
            info = stock.info

            price = float(info["regularMarketPrice"])
            options = stock.options

            vol_aver_10days = info["averageDailyVolume10Day"]
            vol_aver_3months = info["averageDailyVolume3Month"]

        except Exception as e:
            return {}, None, {}, None, None

        return stock, price, options, vol_aver_10days, vol_aver_3months

    def get_high_low_price(self):
        """
        It downloads the Close price in the past 3 months and computes
        the highest, lowest prices and the averages
        :param: none
        :return:
        """
        try:
            data = yf.download(self._symbol, period='3mo', group_by='column')
            if data.empty:
                raise ValueError("No data returned for ticker")
            close_prices = data['Close']
            low = round(close_prices.min()[self._symbol], 2)
            high = round(close_prices.max()[self._symbol], 2)
            avg_price = round(close_prices.mean()[self._symbol], 2)
            avg_price_7d = round(close_prices.tail(7).mean()[self._symbol], 2)
            avg_price_30d = round(close_prices.tail(30).mean()[self._symbol], 2)
            last_price = round(close_prices.iloc[-1][self._symbol], 2)
            first_price = round(close_prices.iloc[0][self._symbol], 2)
            price_trend = functions.get_price_trend(close_prices)
            abs_sd, rel_sd = functions.get_std_dev(self._symbol, close_prices)

        except Exception as e:
            print(f"Download failed: {e}")
            return [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1]

        return [low, high, first_price, last_price, avg_price, avg_price_7d, avg_price_30d, price_trend, abs_sd, rel_sd]





