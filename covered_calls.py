import sys
import time
import functions
import warnings
import pandas as pd
from datetime import datetime
import csv
import Assets
import config

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)


def run(ticker: Assets.Equity,
        option_date,
        threshold_bid: float,
        rel_std_deviation: float,
        std_dev_threshold: float):

    print(f"|-- Scanning the best covered calls in {ticker.exchange} --|")

    stock, current_price, options, sector, industry, beta, vol_aver_10days, vol_aver_3months = ticker.get_info()
    price_data = ticker.get_high_low_price()
    lowest_price, highest_price, first_price, last_price = price_data[0], price_data[1], price_data[2], price_data[3]
    avg_price, avg_price_7d, avg_price_30d = price_data[4], price_data[5], price_data[6]
    trend = price_data[7]

    cc = stock.option_chain(option_date).calls

    if cc is not None:
        cc_contract = cc["contractSymbol"]
        cc_strike = cc["strike"]
        cc_bid = cc["bid"]
        cc_ask = cc["ask"]
        cc_open_interest = cc["openInterest"]
        cc_impl_volatility = round(cc["impliedVolatility"] * 100, 2)

        for i in range(len(cc_contract)):
            spread_bid_ask = round(cc_ask[i] - cc_bid[i], 2)
            spread_strike_price = round(cc_strike[i] - current_price, 2)
            delta_price_premium = round(cc_strike[i] - current_price + cc_bid[i], 2)
            ratio_bid_strike = round((cc_bid[i] / cc_strike[i]) * 100, 2)
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

            best_tickers_with_options = []
            best_contracts_dict = {}

            if cc_bid[i] >= threshold_bid and cc_strike[i] > current_price and rel_std_deviation < std_dev_threshold:
                if ticker.symbol not in best_tickers_with_options:
                    best_tickers_with_options.append(ticker.symbol)
                best_contracts_dict[cc_contract[i]] = [ticker.symbol,
                                                       cc_contract[i],
                                                       option_date,
                                                       current_price,
                                                       rel_std_deviation,
                                                       round(float(delta_price_premium), 2),
                                                       round(float(spread_strike_price), 2),
                                                       round(float(cc_strike[i]), 2),
                                                       round(float(cc_bid[i] * 100), 2),
                                                       round(float(spread_bid_ask), 2),
                                                       cc_open_interest[i],
                                                       cc_impl_volatility[i],
                                                       ratio_bid_strike,  # pivot field
                                                       sector,
                                                       industry,
                                                       highest_price,
                                                       avg_price,
                                                       lowest_price,
                                                       main_trend,
                                                       beta]

            print(best_contracts_dict)


ticker_test = Assets.Equity("AAPL", "NASDAQ")
run(ticker_test, "2026-03-13", 0.3, 12.0, 15.0)
