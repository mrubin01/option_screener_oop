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
    :return: none
    """
    data = yf.Ticker("^VIX")
    info = data.info
    current_vix = info["regularMarketPrice"]

    if current_vix < 15:
        print(f"Volatility index VIX is {current_vix} --> LOW")
        print("------ ------")
    elif 15 <= current_vix < 20:
        print(f"Volatility index VIX is {current_vix} --> MODERATE")
        print("------ ------")
    elif 20 <= current_vix < 30:
        print(f"Be careful! Volatility index VIX is {current_vix} --> HIGH")
        print("------ ------")
    elif 30 <= current_vix < 80:
        print(f"Be careful! Volatility index VIX is {current_vix} --> VERY HIGH")
        print("------ ------")
    elif current_vix >= 80:
        print(f"Be careful! Volatility index VIX is {current_vix} --> EXTREMELY HIGH")
        print("------ ------")



def write_tickers_to_file(tickers: list, filename: str):
    """
    Writes a list of tickers to a TXT file, one ticker per line
    :param tickers: a list of tickers
    :param filename: Output filename, e.g. 'tickers.txt'
    :return: none
    """
    if not filename.endswith(('.txt', '.csv')):
        raise ValueError("Filename must end with .txt or .csv")

    try:
        with open(filename, 'w') as f:
            for ticker in tickers:
                f.write(f"{ticker}\n")
    except Exception as e:
        print(f"Failed to write file: {e}")

