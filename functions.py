import yfinance as yf
from numba import njit
import numpy as np
import requests_cache


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
