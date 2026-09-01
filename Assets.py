import concurrent.futures
import yfinance as yf
import pandas as pd
import functions
import alpaca_client
from alpaca.data.requests import StockLatestTradeRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

_YF_TIMEOUT = 15  # seconds for any yfinance network call


def _yf_call(fn, timeout=_YF_TIMEOUT):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(fn).result(timeout=timeout)


class Asset(object):
    def __init__(self, symbol: str, exchange: str = "Unknown"):
        self.symbol = symbol
        self.exchange = exchange

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

    @property
    def exchange(self):
        return self._exchange

    @exchange.setter
    def exchange(self, new_exchange: str):
        if isinstance(new_exchange, str):
            self._exchange = new_exchange
        else:
            print("Invalid exchange! It must be a string")

    def get_price_stats(self) -> dict:
        try:
            req = StockBarsRequest(
                symbol_or_symbols=self._symbol,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=90),
            )
            bars = alpaca_client.get_stock_bars(req)

            if self._symbol not in bars.data or not bars.data[self._symbol]:
                return {}

            bar_data = bars.data[self._symbol]
            close_prices = pd.Series(
                [b.close for b in bar_data],
                index=[b.timestamp.date() for b in bar_data],
                dtype=float,
            ).dropna()
            if close_prices.empty:
                return {}

            high_prices = pd.Series([b.high for b in bar_data], dtype=float)
            low_prices = pd.Series([b.low for b in bar_data], dtype=float)

            avg_price = round(float(close_prices.mean()), 2)
            avg_price_7d = round(float(close_prices.tail(7).mean()), 2)
            avg_price_30d = round(float(close_prices.tail(30).mean()), 2)
            ma_20 = round(float(close_prices.tail(20).mean()), 2)
            ma_50 = round(float(close_prices.tail(50).mean()), 2)
            high_90d = round(float(high_prices.max()), 2)
            low_90d = round(float(low_prices.min()), 2)
            last_price = round(float(close_prices.iloc[-1]), 2)
            first_price = round(float(close_prices.iloc[0]), 2)
            price_trend = functions.get_price_trend(close_prices.tail(30))
            abs_sd, rel_sd = functions.get_std_dev(self._symbol, close_prices)
            hv = functions.compute_hv(close_prices)

            return {
                "ma_20": ma_20,
                "ma_50": ma_50,
                "high_90d": high_90d,
                "low_90d": low_90d,
                "first_price": first_price,
                "last_price": last_price,
                "avg_price": avg_price,
                "avg_price_7d": avg_price_7d,
                "avg_price_30d": avg_price_30d,
                "price_trend": price_trend,
                "abs_sd": abs_sd,
                "rel_sd": rel_sd,
                "hv": hv,
            }

        except Exception as e:
            print(f"Price download failed for {self._symbol}: {e}")
            return {}


class Equity(Asset):
    def __init__(self, symbol, exchange="Unknown"):
        super(Equity, self).__init__(symbol, exchange)

    def __str__(self):
        return f"{self.symbol} is an equity, its exchange is {self.exchange}"

    def get_info(self) -> dict:
        try:
            req = StockLatestTradeRequest(symbol_or_symbols=self._symbol)
            trade = alpaca_client.get_latest_trades(req)
            if self._symbol not in trade:
                return {}
            price = float(trade[self._symbol].price)

            stock = yf.Ticker(self._symbol)
            options = _yf_call(lambda: stock.options)
            if not options:
                return {}

            return {
                "price": price,
                "options": options,
            }

        except Exception:
            return {}


class ETF(Asset):
    def __init__(self, symbol, exchange="Unknown"):
        super(ETF, self).__init__(symbol, exchange)

    def __str__(self):
        return f"{self.symbol} is an ETF, its exchange is {self.exchange}"

    def get_info_etf(self):
        try:
            req = StockLatestTradeRequest(symbol_or_symbols=self._symbol)
            trade = alpaca_client.get_latest_trades(req)
            if self._symbol not in trade:
                return {}
            price = float(trade[self._symbol].price)

            stock = yf.Ticker(self._symbol)
            options = _yf_call(lambda: stock.options)
            if not options:
                return {}

            return {
                "price": price,
                "options": options,
            }

        except Exception:
            return {}


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
