import concurrent.futures
import json
import yfinance as yf
import numpy as np
from sklearn.linear_model import LinearRegression
import pandas as pd
import math
from py_vollib.black_scholes.greeks.analytical import delta
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import alpaca_client
from alpaca.data.requests import OptionChainRequest
from alpaca.data.enums import OptionsFeed
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


def get_alpaca_option_chain_bulk(symbol: str, target_dates: set[str] | None = None) -> dict[tuple[str, str], pd.DataFrame]:
    """
    Fetch the full option chain for a symbol in one Alpaca API call (all expiries, both types).
    Returns {(expiry_date, "call"|"put"): DataFrame}.  OI is fetched from yfinance in parallel
    across all expiry dates (one yfinance call per expiry instead of one per expiry+type).
    """
    try:
        req = OptionChainRequest(
            underlying_symbol=symbol,
            feed=OptionsFeed.INDICATIVE,
        )
        chain = alpaca_client.get_option_chain(req)
    except Exception:
        return {}

    if not chain:
        return {}

    # Parse contract symbols to extract expiry and type.
    # OCC format: {ticker}{YYMMDD}{C|P}{8-digit-strike}
    # The last 15 chars are always YYMMDD + C|P + 00000000
    contracts_by_key: dict[tuple[str, str], list] = {}
    for contract_sym, snap in chain.items():
        if snap.latest_quote is None:
            continue
        if not snap.implied_volatility:
            continue
        try:
            date_part = contract_sym[-15:-9]          # YYMMDD
            type_char = contract_sym[-9]               # C or P
            expiry = f"20{date_part[:2]}-{date_part[2:4]}-{date_part[4:]}"
            opt_type = "call" if type_char == "C" else "put"
        except Exception:
            continue
        if target_dates is not None and expiry not in target_dates:
            continue
        key = (expiry, opt_type)
        contracts_by_key.setdefault(key, []).append({
            "contractSymbol": contract_sym,
            "bid": snap.latest_quote.bid_price or 0.0,
            "ask": snap.latest_quote.ask_price or 0.0,
            "strike": int(contract_sym[-8:]) / 1000,
            "impliedVolatility": snap.implied_volatility,
            "openInterest": 0,
        })

    if not contracts_by_key:
        return {}

    # Fetch OI from yfinance once per unique expiry (covers both calls and puts)
    unique_expiries = list({exp for exp, _ in contracts_by_key})

    def _fetch_yf_expiry(exp: str) -> dict[str, int]:
        try:
            def _inner():
                yf_chain = yf.Ticker(symbol).option_chain(exp)
                result: dict[str, int] = {}
                for df in [yf_chain.calls, yf_chain.puts]:
                    if df is not None and not df.empty and "openInterest" in df.columns:
                        result.update(
                            df.set_index("contractSymbol")["openInterest"]
                            .fillna(0)
                            .astype(int)
                            .to_dict()
                        )
                return result
            alpaca_client._yf_limiter.acquire()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(_inner).result(timeout=20)
        except Exception:
            return {}

    oi_map: dict[str, int] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_fetch_yf_expiry, exp): exp for exp in unique_expiries}
        for f in concurrent.futures.as_completed(futures):
            try:
                oi_map.update(f.result())
            except Exception:
                pass

    result: dict[tuple[str, str], pd.DataFrame] = {}
    for key, rows in contracts_by_key.items():
        for row in rows:
            row["openInterest"] = oi_map.get(row["contractSymbol"], 0)
        result[key] = pd.DataFrame(rows)

    return result


def get_alpaca_option_chain(symbol: str, expiry_date: str, option_type: str) -> pd.DataFrame:
    ct = ContractType.CALL if option_type.lower() in ("call", "calls", "c") else ContractType.PUT
    try:
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date=expiry_date,
            type=ct,
            feed=OptionsFeed.INDICATIVE,
        )
        chain = alpaca_client.get_option_chain(req)
    except Exception:
        return pd.DataFrame()

    if not chain:
        return pd.DataFrame()

    oi_map = {}
    try:
        def _fetch_yf(sym, exp, call_type):
            chain = yf.Ticker(sym).option_chain(exp)
            return chain.calls if call_type == ContractType.CALL else chain.puts

        alpaca_client._yf_limiter.acquire()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_fetch_yf, symbol, expiry_date, ct)
            yf_df = fut.result(timeout=20)

        if yf_df is not None and not yf_df.empty and "openInterest" in yf_df.columns:
            oi_map = (
                yf_df.set_index("contractSymbol")["openInterest"]
                .fillna(0)
                .astype(int)
                .to_dict()
            )
    except Exception:
        pass

    rows = []
    for contract_sym, snap in chain.items():
        if snap.latest_quote is None:
            continue
        if not snap.implied_volatility:
            continue
        rows.append({
            "contractSymbol": contract_sym,
            "bid": snap.latest_quote.bid_price or 0.0,
            "ask": snap.latest_quote.ask_price or 0.0,
            "strike": int(contract_sym[-8:]) / 1000,
            "impliedVolatility": snap.implied_volatility,
            "openInterest": oi_map.get(contract_sym, 0),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def compute_hv(close_prices: pd.Series) -> float:
    log_returns = np.log(close_prices / close_prices.shift(1)).dropna()
    if log_returns.empty:
        return 0.0
    return round(float(log_returns.std() * np.sqrt(252)), 4)


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



def compute_main_trend(
    current_price: float,
    avg_price: float,
    avg_price_7d: float,
    avg_price_30d: float,
    trend: int,
) -> int:
    below_recent = current_price < avg_price_7d and current_price < avg_price_30d
    above_recent = current_price > avg_price_7d and current_price > avg_price_30d

    if above_recent and trend == 1:
        return 1   # TREND_UP
    if below_recent and trend == 0:
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


def write_best_options_to_json(path: str, exchange_no: int, sorted_option_list: list[dict], buying_side: bool = False):
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
            "ma_20",
            "ma_50",
            "high_90d",
            "low_90d",
            "main_trend",
            "beta",
            "iv_hv_ratio",
            "ex_dividend_date",
            "earnings_date",
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
            "ma_20",
            "ma_50",
            "high_90d",
            "low_90d",
            "main_trend",
            "iv_hv_ratio",
            "ex_dividend_date",
            "earnings_date",
        ]
    else:
        raise ValueError("Wrong exchange number!")

    if buying_side:
        remove = {"max_profit", "max_profit_per_contract", "tot_return", "option_yield", "roc"}
        keys = [k for k in keys if k not in remove]
        keys = ["ask_per_share" if k == "bid_per_share" else k for k in keys]
        keys = keys + ["profit_5pct", "return_5pct", "profit_10pct", "return_10pct"]

    data = []
    for row in sorted_option_list:
        item = {key: row.get(key) for key in keys}
        # item["expiry_date"] = row["strike_date"]
        data.append(item)

    with open(path, "w") as jsonfile:
        json.dump(data, jsonfile, indent=2)
