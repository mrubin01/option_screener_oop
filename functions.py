import sys
import json
import yfinance as yf
import numpy as np
import requests_cache
from sklearn.linear_model import LinearRegression
import csv
import pandas as pd
import math
from py_vollib.black_scholes.greeks.analytical import delta
from datetime import date, datetime


def days_to_expiration(expiration_date: str, today: date | None = None) -> int:
    """
    Calculate calendar days from today to an option expiration date.

    Parameters
    ----------
    expiration_date : str
        Expiration date in 'YYYY-MM-DD' format.
        Example: '2026-05-01'
    today : date | None
        Optional custom start date. Defaults to today's date.

    Returns
    -------
    int
        Number of calendar days until expiration.
    """

    if today is None:
        today = date.today()

    expiry = datetime.strptime(expiration_date, "%Y-%m-%d").date()

    return (expiry - today).days


def normalize_rate(value: float) -> float:
    """
    Accepts either:
    - 3.68 for 3.68%
    - 0.0368 for 3.68%
    """
    value = float(value)
    return value / 100 if value > 1 else value


def normalize_iv(value: float) -> float:
    """
    Accepts IV in common formats:
    - 115.23 means 115.23%
    - 1.1523 means 115.23%
    - 0.4263 means 42.63%
    """
    value = float(value)

    if value > 3:
        return value / 100

    return value


def estimate_delta(
    strategy: str,
    current_price: float,
    strike_price: float,
    days: int,
    risk_free_rate: float,
    impl_volatility: float,
    decimals: int = 2,
) -> str:
    strategy = strategy.lower().strip()

    S = float(current_price)
    K = float(strike_price)
    t = float(days) / 365
    r = normalize_rate(risk_free_rate)
    sigma = normalize_iv(impl_volatility)

    if strategy in ["covered_call", "cc", "call", "calls", "c"]:
        option_type = "c"
    elif strategy in ["cash_secured_put", "csp", "put", "puts", "p"]:
        option_type = "p"
    else:
        raise ValueError(
            "strategy must be 'covered_call', 'cc', 'cash_secured_put', or 'csp'"
        )

    option_delta = float(delta(option_type, S, K, t, r, sigma))
    probability = abs(option_delta) * 100

    return f"{probability:.{decimals}f}"


def normalize_nullable_fields(value):
    """It returns null instead of NaN or an empty string"""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None

    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None

    return text


def get_std_dev(ticker: str, price_list: pd.DataFrame | pd.Series) -> list[float]:
    """
    Starting from a DataFrame/Series of stock prices, calculate the absolute
    and relative (%) standard deviation.

    :param ticker: the stock ticker
    :param price_list: pandas DataFrame or Series of stock prices
    :return: [abs_std_dev, rel_std_dev]
    """
    try:
        if price_list is None or len(price_list) == 0:
            return [-1, -1]

        # If a DataFrame is passed, extract the ticker column if present.
        # Otherwise, if it has only one column, use that column.
        if isinstance(price_list, pd.DataFrame):
            if ticker in price_list.columns:
                prices = price_list[ticker]
            elif price_list.shape[1] == 1:
                prices = price_list.iloc[:, 0]
            else:
                return [-1, -1]
        else:
            prices = price_list

        prices = prices.dropna()
        if prices.empty:
            return [-1, -1]

        abs_std_dev = float(prices.std())
        avg_close_price = float(prices.mean())

        if avg_close_price == 0:
            return [-1, -1]

        rel_std_dev = (abs_std_dev / avg_close_price) * 100

        return [round(abs_std_dev, 2), round(rel_std_dev, 2)]

    except Exception:
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


def get_index_change_last5d(index_ticker: str, period: str = "5d"):
    data = yf.download(index_ticker, period=period, group_by='column')
    close_prices = data['Close']
    last_price = get_last_index_price(index_ticker)
    first_price = round(close_prices.iloc[0][index_ticker], 2)

    if index_ticker == "^FTSE" or index_ticker == "^DJI":
        change = round(((last_price - first_price) / first_price) * 100, 2)
        return change
    else:
        print("Wrong Index ticker!")
        sys.exit()


def get_last_index_price(index_ticker):
    data = yf.Ticker(index_ticker)
    info = data.info
    current_index = info["regularMarketPrice"]

    return current_index


def get_vix():
    """"
    It checks for the current volatility index VIX
    :param none
    :return: none
    """
    data = yf.Ticker("^VIX")
    info = data.info
    current_vix = info["regularMarketPrice"]

    if current_vix < 15:
        print(f"|-- Volatility index VIX is {current_vix} --> LOW --|")
    elif 15 <= current_vix < 20:
        print(f"|-- Volatility index VIX is {current_vix} --> MODERATE --|")
    elif 20 <= current_vix < 30:
        print(f"|-- WARNING: Volatility index VIX is {current_vix} --> HIGH --|")
    elif 30 <= current_vix < 80:
        print(f"|-- WARNING: Volatility index VIX is {current_vix} --> VERY HIGH --|")
    elif current_vix >= 80:
        print(f"|-- WARNING: Volatility index VIX is {current_vix} --> EXTREMELY HIGH --|")


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


def write_best_option_to_file(path: str, exchange: int, sorted_option_list: list):
    """
    This function has been replaced

    Write a list of option into a directory as a csv file
    :param path: a string with the path
    :param exchange: 0 NYSE, 1 NASDAQ, 2, ARCA
    :param sorted_option_list: a lsit with the best options
    :return: none
    """
    if exchange in [0, 1]:
        with open(path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "sector", "industry", "highest", "avg price", "lowest", "beta"])
            for row in sorted_option_list:
                writer.writerow([row[0], row[1], row[3], row[6], row[-10], row[-7], row[-6], row[-5], row[-4], row[-3], row[-2], row[-1]])
    elif exchange == 2:
        with open(path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "highest", "avg price", "lowest", "trend"])
            for row in sorted_option_list:
                writer.writerow([row[0], row[1], row[3], row[6], row[-8], row[-5], row[-4], row[-3], row[-2], row[-1]])
    else:
        print("Impossible to write options to file! Wrong exchange number")


def write_best_option_to_file_updated(path: str, exchange: int, sorted_option_list: list, output_format: str):
    """This function has been replaced"""
    output_format = output_format.lower()

    if exchange in [0, 1] and output_format == "csv":
        with open(path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "sector", "industry", "highest", "avg price", "lowest", "beta"])
            for row in sorted_option_list:
                writer.writerow([row[0], row[1], row[3], row[6], row[-10], row[-7], row[-6], row[-5], row[-4], row[-3], row[-2], row[-1]])
    elif exchange == 2 and output_format == "csv":
        with open(path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "highest", "avg price", "lowest", "trend"])
            for row in sorted_option_list:
                writer.writerow([row[0], row[1], row[3], row[6], row[-8], row[-5], row[-4], row[-3], row[-2], row[-1]])

    elif exchange in [0, 1] and output_format == "json":
        data = [
            {
                "contract": row[0],
                "expiry_date": row[1],
                "current_price": row[3],
                "strike_price": row[6],
                "premium": row[-10],
                "ratio": row[-7],
                "sector": row[-6],
                "industry": row[-5],
                "highest": row[-4],
                "avg price": row[-3],
                "lowest": row[-2],
                "beta": row[-1]
            }
            for row in sorted_option_list
        ]
        with open(path, "w") as jsonfile:
            json.dump(data, jsonfile, indent=2)
    elif exchange == 2 and output_format == "json":

        # writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "highest", "avg price", "lowest", "trend"])
        # writer.writerow([row[0], row[1], row[3], row[6], row[-8], row[-5], row[-4], row[-3], row[-2], row[-1]])

        data = [
            {
                "contract": row[0],
                "expiry_date": row[1],
                "current_price": row[3],
                "strike_price": row[6],
                "premium": row[-8],
                "ratio": row[-5],
                "highest": row[-4],
                "avg price": row[-3],
                "lowest": row[-2],
                "trend": row[-1]
            }
            for row in sorted_option_list
        ]
        with open(path, "w") as jsonfile:
            json.dump(data, jsonfile, indent=2)

    else:
        raise ValueError("output_format must be 'csv' or 'json'")


def write_best_options_to_json(path: str, exchange_no: int, sorted_option_list: list[dict]):
    if exchange_no in [0, 1]:
        keys = [
            "ticker",
            "exchange",
            "contract",
            "expiry_date",
            "days_to_expiration",
            "current_price",
            "coeff_variation",
            "max_profit",
            "max_profit_per_contract",
            "otm",
            "strike_price",
            "bid_per_share",
            "premium_per_contract",
            "spread_bid_ask",
            "break_even",
            "open_interest",
            "impl_volatility",
            "option_yield",
            "roc",
            "tot_return",
            "delta",
            "sector",
            "industry",
            "highest_price",
            "avg_price",
            "lowest_price",
            "main_trend",
            "beta",
        ]
    elif exchange_no == 2:
        keys = [
            "ticker",
            "exchange",
            "contract",
            "expiry_date",
            "days_to_expiration",
            "current_price",
            "coeff_variation",
            "max_profit",
            "max_profit_per_contract",
            "otm",
            "strike_price",
            "bid_per_share",
            "premium_per_contract",
            "spread_bid_ask",
            "break_even",
            "open_interest",
            "impl_volatility",
            "option_yield",
            "roc",
            "tot_return",
            "delta",
            "highest_price",
            "avg_price",
            "lowest_price",
            "main_trend",
        ]
    else:
        raise ValueError("Wrong exchange number!")

    data = []
    for row in sorted_option_list:
        item = {key: row[key] for key in keys}
        # item["expiry_date"] = row["strike_date"]
        data.append(item)

    with open(path, "w") as jsonfile:
        json.dump(data, jsonfile, indent=2)
