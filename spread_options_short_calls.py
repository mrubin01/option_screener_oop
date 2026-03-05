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

tickers_with_options = []
best_tickers_with_options = []
best_contracts_dict = {}

"""
Relative standard deviation or Coefficient of variation (CoV) measures the deviation between the historical mean 
price and the current price performance of a financial asset. In short, it measures its volatility
The formula is (std_dev / mean price) * 100

CoV < 2 LOW, CoV < 5 MODERATE, CoV >= 5 HIGH, CoV >= 10 VERY HIGH

It seems that, for the spread options in ARCA, the best contracts are those with a CoV < 10%
"""

# TREND is not defined for this at the moment


def run(year_short: int, month_short: list, day_short: list, exchange: int, tickers: list):
    start_time = time.time()

    if exchange != 2:
        print("Only ARCA is accepted!")
        sys.exit()

    if not isinstance(year_short, int) or \
            not isinstance(month_short, list) or \
            not isinstance(day_short, list) or \
            not isinstance(tickers, list):
        print("Something is wrong with the parameters!")
        sys.exit()

    print(f"|-- Scanning the best short covered call... --|")
    print()

    for t in tickers:
        print(t)
        ticker = Assets.ETF(t, config.EXCHANGES[exchange])
        stock, price, options, vol_aver_10days, vol_aver_3months = ticker.get_info_etf()

        if len(options) >= 10 and price <= config.MAX_STOCK_PRICE:
            if t not in tickers_with_options:
                tickers_with_options.append(t)

            try:
                price_data = ticker.get_high_low_price()
                lowest_price, highest_price, first_price, last_price = price_data[0], price_data[1], price_data[2], price_data[3]
                avg_price, avg_price_7d, avg_price_30d = price_data[4], price_data[5], price_data[6]
                trend = price_data[7]
                # rel_std_deviation aka coefficient of variation: rel_std < 2 LOW, rel_std < 5 MODERATE, rel_std >= 5 HIGH, >= 10 VERY HIGH
                abs_std_deviation, rel_std_deviation = price_data[8], price_data[9]
                lowest_decrease = round((lowest_price / price) * 100, 2)
                highest_increase = round((highest_price / price) * 100, 2)
            except Exception as e:
                continue

            for d in options:
                new_date = datetime.strptime(d, "%Y-%m-%d")
                day = new_date.day
                month = new_date.month
                year = new_date.year

                # ARCA - spread options
                if year == year_short and month in month_short and day in day_short:  # and TYPE == 2:
                    try:
                        cc = stock.option_chain(d).calls

                        if cc is not None:
                            cc_contract = cc["contractSymbol"]
                            cc_strike = cc["strike"]
                            cc_bid = cc["bid"]
                            cc_ask = cc["ask"]
                            cc_vol = cc["volume"]
                            cc_open_interest = cc["openInterest"]
                            cc_impl_volatility = round(cc["impliedVolatility"] * 100, 2)

                            for i in range(len(cc_contract)):
                                spread_bid_ask = round(cc_ask[i] - cc_bid[i], 2)
                                spread_strike_price = round(cc_strike[i] - price, 2)
                                delta_price_premium = round(cc_strike[i] - price + cc_bid[i], 2)
                                # for cov calls usually you sell a call, then the bid price is used
                                ratio_bid_strike = round((cc_bid[i] / cc_strike[i]) * 100, 2)
                                print(f"{t} std_dev {abs_std_deviation} / avg_price {avg_price} = rel_std_dev = {rel_std_deviation}")

                                if spread_strike_price >= 1.5 and float(cc_bid[i]) >= 0.5:
                                    print(f"bid {cc_bid[i]} / strike {cc_strike[i]} = ratio {ratio_bid_strike}")
                                    # for the short call, the bid price is used
                                    # ratio_bid_strike = round((cc_bid[i] / cc_strike[i]) * 100, 2)

                                    # price_vs_avgs = -1
                                    # if price < avg_price and price < avg_price_7d and price < avg_price_30d:
                                    #     price_vs_avgs = 0  # price is lower than the averages
                                    # if price > avg_price and price > avg_price_7d and price > avg_price_30d:
                                    #     price_vs_avgs = 1  # price is higher than the averages

                                    if cc_bid[i] >= config.MIN_BID_PRICE and rel_std_deviation < config.STD_DEV_THRESHOLD:
                                        if t not in best_tickers_with_options:
                                            best_tickers_with_options.append(t)

                                        best_contracts_dict[cc_contract[i]] = [cc_contract[i], d, t, price, round(float(delta_price_premium), 2),
                                                                               round(float(spread_strike_price), 2), round(float(cc_strike[i]), 2),
                                                                                round(float(cc_bid[i] * 100), 2), cc_open_interest[i],
                                                                                cc_impl_volatility[i], ratio_bid_strike,  # ratio_bid_strike,
                                                                                highest_price, avg_price, lowest_price, trend]

                                        print(f"Short CC Match: {cc_contract[i]}; strike {cc_strike[i]} > price: {price}; bid: {cc_bid[i]} --> ratio {ratio_bid_strike}")
                                        print(f"Spread Strike - Current price: {spread_strike_price}; Trend: {trend}")
                                        print()
                    except Exception as e:
                        continue

    sorted_best_contracts = sorted(best_contracts_dict.values(), key=lambda x: x[-5], reverse=False)

    # all tickers with active options
    if config.WRITE_TICKERS_TO_FILE == 1 and config.SCOPE == 1 and exchange == 2:
        functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_arca.txt")
    else:
        print("Check tickers with options")

    functions.write_best_option_to_file("/Users/madararubino/best_options/test_arca_spread_short_calls.csv", exchange, sorted_best_contracts)

    end_time = time.time()
    execution_time = end_time - start_time
    print("--- EXECUTION TIME ---")
    print(f"--> {execution_time:.3f} seconds")
    print(f"--> {execution_time / 60:.2f} minutes")


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")


