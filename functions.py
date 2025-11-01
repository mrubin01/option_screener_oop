import yfinance as yf
import numpy as np
import requests_cache
from sklearn.linear_model import LinearRegression


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
