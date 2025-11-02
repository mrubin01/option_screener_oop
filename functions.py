import yfinance as yf
import numpy as np
import requests_cache
from sklearn.linear_model import LinearRegression


def get_std_dev(ticker: str, price_list: list) -> list:
    """
    Starting from a list of stock prices, it calculates the absolute and the relative (%) std deviation
    :param ticker: the stock ticker
    :param price_list: a list of stock prices
    :return: a list with abs and relative std deviation
    """
    try:
        std_dev = price_list.std()
        abs_std_dev = std_dev[ticker]

        # last_close_price = price_list.iloc[-1][ticker]
        avg_close_price = price_list.mean()[ticker]

        # rel_std_dev = (abs_std_dev / last_close_price) * 100
        rel_std_dev = (abs_std_dev / avg_close_price) * 100

        return [round(abs_std_dev, 2), round(rel_std_dev, 2)]
    except Exception as e:
        return [-1, -1]


def get_price_trend(price_list: list):
    """
    Based on the price list, it calculates the trend: 1 uptrend, 0 downtrend
    :param price_list:
    :return:
    """
    X = np.arange(len(price_list)).reshape(-1, 1)
    y = price_list.values.reshape(-1, 1)
    model = LinearRegression().fit(X, y)
    slope = model.coef_[0][0]
    trend = 1 if slope > 0 else 0

    return trend


def create_user_agent():
    session = requests_cache.CachedSession('yfinance.cache')
    session.headers['User-Agent'] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0"

    return session


def get_vix():
    """"
    It checks for the volatility index VIX
    :param none
    :return: float
    """
    data = yf.Ticker("^VIX")
    info = data.info
    current = info["regularMarketPrice"]

    return round(float(current), 2)
