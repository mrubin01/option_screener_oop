import warnings
import pandas as pd
import yfinance

import Assets
from typing import Any


warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)


def run(
    ticker: Assets.Equity,
    option_date: str,
    threshold_bid: float,
    std_dev_threshold: float,
    stock: yfinance.Ticker,
    current_price: float,
    sector: str,
    industry: str,
    beta: float,
    lowest_price: float,
    highest_price: float,
    avg_price: float,
    avg_price_7d: float,
    avg_price_30d: float,
    trend: int,
    rel_std_deviation: float
) -> list[dict[str, Any]]:

    if threshold_bid < 0:
        raise ValueError("threshold_bid must be non-negative")
    if std_dev_threshold < 0:
        raise ValueError("std_dev_threshold must be non-negative")

    try:
        cc = stock.option_chain(option_date).calls
    except Exception as e:
        # log and return empty list
        return []

    # contract = {}
    all_contracts = []

    if cc is None or cc.empty:
        return []
    else:
        cc_contract = cc["contractSymbol"]
        cc_strike = cc["strike"]
        cc_bid = cc["bid"]
        cc_ask = cc["ask"]
        cc_open_interest = cc["openInterest"]
        cc_impl_volatility = round(cc["impliedVolatility"] * 100, 2)

        for i in range(len(cc_contract)):
            spread_bid_ask = round(cc_ask.iloc[i] - cc_bid.iloc[i], 2)
            spread_strike_price = round(cc_strike.iloc[i] - current_price, 2)
            delta_price_premium = round(cc_strike.iloc[i] - current_price + cc_bid.iloc[i], 2)
            ratio_bid_strike = round((cc_bid.iloc[i] / cc_strike.iloc[i]) * 100, 2)
            price_vs_avgs = -1
            if current_price < avg_price and current_price < avg_price_7d and current_price < avg_price_30d:
                price_vs_avgs = 0  # price is lower than the averages
            if current_price > avg_price and current_price > avg_price_7d and current_price > avg_price_30d:
                price_vs_avgs = 1  # price is higher than the averages

            # main_trend
            main_trend = 0  # sideways
            if price_vs_avgs == 1 and trend == 1:
                main_trend = 1  # uptrend
            elif price_vs_avgs == 0 and trend == 0:
                main_trend = -1  # downtrend

            if cc_bid.iloc[i] >= threshold_bid and cc_strike.iloc[i] > current_price and rel_std_deviation < std_dev_threshold:
                # This must be in the main, not here
                # if ticker.symbol not in best_tickers_with_options:
                #     best_tickers_with_options.append(ticker.symbol)

                contract = dict(
                    symbol=ticker.symbol,
                    contract=cc_contract.iloc[i],
                    strike_date=option_date,
                    current_price=current_price,
                    rel_std_deviation=rel_std_deviation,
                    spread_premium_price_and_bid=round(float(delta_price_premium), 2),
                    spread_strike_price=round(float(spread_strike_price), 2),
                    strike_price=round(float(cc_strike[i]), 2),
                    bid=round(float(cc_bid[i] * 100), 2),
                    spread_bid_ask=round(float(spread_bid_ask), 2),
                    open_interest=cc_open_interest[i],
                    impl_volatility=cc_impl_volatility[i],
                    ratio_bid_strike=ratio_bid_strike,  # pivot field
                    sector=sector,
                    industry=industry,
                    highest_price=highest_price,
                    avg_price=avg_price,
                    lowest_price=lowest_price,
                    main_trend=main_trend,
                    beta=beta
                )

                all_contracts.append(contract[cc_contract.iloc[i]])

    # sort contracts based on the ratio bid/strike price
    all_contracts_sorted = sorted(all_contracts, key=lambda x: x["ratio_bid_strike"], reverse=True)

    return all_contracts_sorted


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")

