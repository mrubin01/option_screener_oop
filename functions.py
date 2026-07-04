import sys
import json
import yfinance as yf
import numpy as np
import requests_cache
from sklearn.linear_model import LinearRegression
import pandas as pd
import math
from py_vollib.black_scholes.greeks.analytical import delta
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import alpaca_client
from alpaca.data.requests import OptionChainRequest
from alpaca.trading.enums import ContractType


def sigma_distance_to_strike(
    current_price: float,
    strike_price: float,
    implied_volatility: float,
    days_left: int,
    days_in_year: int = 365
) -> float:
    """
    Calculate the sigma distance to strike.

    Parameters
    ----------
    current_price : float
        Current underlying price.
    strike_price : float
        Option strike price.
    implied_volatility : float
        Annualized IV as a decimal, e.g. 0.40 for 40%.
    days_left : int
        Days to expiration.
    days_in_year : int
        Use 365 for calendar days, or 252 for trading days.

    Returns
    -------
    float
        Distance to strike in implied standard deviations.
    """
    if current_price <= 0:
        raise ValueError("current_price must be positive.")
    if strike_price <= 0:
        raise ValueError("strike_price must be positive.")
    if implied_volatility <= 0:
        raise ValueError("implied_volatility must be positive.")
    if days_left <= 0:
        raise ValueError("days_to_expiration must be positive.")

    time_to_expiration = days_left / days_in_year

    return abs(math.log(current_price / strike_price)) / (
        implied_volatility * math.sqrt(time_to_expiration)
    )


def is_at_least_3_months_after_today(date_string: str) -> bool:
    """
    Returns True if date_string is at least 3 months after today.

    Example:
    today = 2026-05-11
    date_string = "2026-08-02" -> True
    date_string = "2026-07-30" -> False
    """

    other_date = datetime.strptime(date_string, "%Y-%m-%d").date()
    three_months_from_today = date.today() + relativedelta(months=3)

    return other_date >= three_months_from_today


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


def normalize_nullable_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_alpaca_option_chain(symbol: str, expiry_date: str, option_type: str) -> pd.DataFrame:
    ct = ContractType.CALL if option_type.lower() in ("call", "calls", "c") else ContractType.PUT
    try:
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date=expiry_date,
            type=ct,
        )
        chain = alpaca_client.get_option_chain(req)
    except Exception:
        return pd.DataFrame()

    if not chain:
        return pd.DataFrame()

    rows = []
    for contract_sym, snap in chain.items():
        if snap.latest_quote is None:
            continue
        rows.append({
            "contractSymbol": contract_sym,
            "bid": snap.latest_quote.bid_price or 0.0,
            "ask": snap.latest_quote.ask_price or 0.0,
            "strike": int(contract_sym[-8:]) / 1000,
            "impliedVolatility": snap.implied_volatility or 0.0,
            "openInterest": 0,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


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
    first_price = round(close_prices.iloc[0][index_ticker], 2)
    last_price = round(close_prices.iloc[-1][index_ticker], 2)

    if index_ticker == "^FTSE" or index_ticker == "^DJI":
        change = round(((last_price - first_price) / first_price) * 100, 2)
        return change
    else:
        print("Wrong Index ticker!")
        sys.exit()



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


def compute_main_trend(
    current_price: float,
    avg_price: float,
    avg_price_7d: float,
    avg_price_30d: float,
    trend: int,
) -> int:
    below_all = current_price < avg_price and current_price < avg_price_7d and current_price < avg_price_30d
    above_all = current_price > avg_price and current_price > avg_price_7d and current_price > avg_price_30d

    if above_all and trend == 1:
        return 1   # TREND_UP
    if below_all and trend == 0:
        return -1  # TREND_DOWN
    return 0       # TREND_SIDEWAYS


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
            "moneyness",
            "sigma_distance",
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
            "moneyness",
            "sigma_distance",
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
