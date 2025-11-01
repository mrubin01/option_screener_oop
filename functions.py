import yfinance as yf
from numba import njit
import numpy as np


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
