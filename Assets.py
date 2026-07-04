import yfinance as yf
import functions
import alpaca_client
from alpaca.data.requests import StockLatestTradeRequest


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
            data = yf.download(self._symbol, period="3mo", group_by="column", progress=False)

            if data is None or data.empty:
                return {}

            if "Close" not in data:
                return {}

            close_prices = data["Close"]

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


class Equity(Asset):
    def __init__(self, symbol, exchange="Unknown"):
        super(Equity, self).__init__(symbol, exchange)

    def __str__(self):
        return f"{self.symbol} is an equity, its exchange is {self.exchange}"

    def get_info(self) -> dict:
        try:
            req = StockLatestTradeRequest(symbol_or_symbols=self._symbol)
            trade = alpaca_client.stock_client.get_stock_latest_trade(req)
            if self._symbol not in trade:
                return {}
            price = float(trade[self._symbol].price)

            # yfinance retained for options list and fundamentals only
            stock = yf.Ticker(self._symbol)
            options = stock.options
            if not options:
                return {}

            info = stock.info
            if not info or not isinstance(info, dict):
                return {}

            return {
                "stock": stock,
                "price": price,
                "options": options,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "beta": info.get("beta"),
                "vol_aver_10days": info.get("averageDailyVolume10Day"),
                "vol_aver_3months": info.get("averageDailyVolume3Month"),
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
            trade = alpaca_client.stock_client.get_stock_latest_trade(req)
            if self._symbol not in trade:
                return {}
            price = float(trade[self._symbol].price)

            # yfinance retained for options list only; no .info call needed for ETFs
            stock = yf.Ticker(self._symbol)
            options = stock.options
            if not options:
                return {}

            return {
                "stock": stock,
                "price": price,
                "options": options,
            }

        except Exception:
            return {}


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
