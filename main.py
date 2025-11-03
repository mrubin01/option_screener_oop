import sys
import time
import functions
import warnings
import pandas as pd
from datetime import datetime
import csv
import Assets

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

user_agent = functions.create_user_agent()

# empty the cache only the first run of the day
CLEAR_CACHE = False
if CLEAR_CACHE:
    user_agent.cache.clear()

start_time = time.time()

functions.get_vix()

# main global variables
TYPE = 0  # 0 call, 1 put, 2 spread
STOCK_EXCHANGE = 0  # nyse, nasdaq, arca
TREND = -1  # -1 no trend, 0 downtrend, 1 uptrend
MAX_STOCK_PRICE = 1000
YEAR, MONTH, DAY = 2025, 11, [7, 14]
STD_DEV_THRESHOLD = 10

OPTION_TYPE = ["Call", "Put", "Spread"]
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]
SCOPE = 0  # 0 only tickers with options, 1 whole ticker list
WRITE_TICKERS_TO_FILE = 1
MIN_BID_PRICE = 0.2
TREND_TYPE = ["downtrend", "uptrend", "no trend"]
HAVE_OPTIONS = 0  # 0 no active options, 1 with active options


match (STOCK_EXCHANGE, SCOPE):
    case (0, 0):
        my_file = open("/Users/madararubino/stocks_with_options_nyse.txt", "r")
    case (1, 0):
        my_file = open("/Users/madararubino/stocks_with_options_nasdaq.txt", "r")
    case (2, 0):
        my_file = open("/Users/madararubino/stocks_with_options_arca.txt", "r")
    case (0, 1):
        my_file = open("/Users/madararubino/shared_data/nyse_tickers_last.txt", "r")
    case (1, 1):
        my_file = open("/Users/madararubino/shared_data/nasdaq_tickers_last.txt", "r")
    case (2, 1):
        my_file = open("/Users/madararubino/shared_data/nyse_arca_tickers_last.txt")
    case _:
        print("Wrong values!")
        sys.exit()

data = my_file.read()
data_into_list = data.replace('\n', ', ').split(", ")
ticker_list = list(filter(None, data_into_list))

tickers_with_options = []
best_tickers_with_options = []
best_contracts_dict = {}

if STOCK_EXCHANGE in [0, 1]:
    print(f"|-- Scanning {OPTION_TYPE[TYPE]} options in {EXCHANGES[STOCK_EXCHANGE]} with {TREND_TYPE[TREND]}...--|")
    print()
    for t in ticker_list:
        ticker = Assets.Equity(t, EXCHANGES[STOCK_EXCHANGE])
        stock, price, options, sector, industry, beta, vol_aver_10days, vol_aver_3months = ticker.get_info()
        if len(options) > 0 and price <= MAX_STOCK_PRICE:
            if t not in tickers_with_options:
                tickers_with_options.append(t)

            price_data = ticker.get_high_low_price()
            lowest_price, highest_price, first_price, last_price = price_data[0], price_data[1], price_data[2], price_data[3]
            avg_price, avg_price_7d, avg_price_30d = price_data[4], price_data[5], price_data[6]
            trend = price_data[7]
            # rel_std_deviation aka coefficient of variation: rel_std < 2 LOW, rel_std < 5 MODERATE, rel_std >= 5 HIGH, >= 10 VERY HIGH
            abs_std_deviation, rel_std_deviation = price_data[8], price_data[9]

            lowest_decrease = round((lowest_price / price) * 100, 2)
            highest_increase = round((highest_price / price) * 100, 2)

            for d in options:
                new_date = datetime.strptime(d, "%Y-%m-%d")
                day = new_date.day
                month = new_date.month
                year = new_date.year

                if year == YEAR and month == MONTH and day in DAY and TYPE == 0:
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
                                ratio_bid_price = round((cc_bid[i] / price) * 100, 2)
                                price_vs_avgs = -1
                                if price < avg_price and price < avg_price_7d and price < avg_price_30d:
                                    price_vs_avgs = 0  # price is lower than the averages
                                if price > avg_price and price > avg_price_7d and price > avg_price_30d:
                                    price_vs_avgs = 1  # price is higher than the averages

                                # stocks with downtrend
                                if TREND == 0:
                                    if cc_bid[i] >= MIN_BID_PRICE \
                                            and cc_strike[i] > price \
                                            and price_vs_avgs == 0 \
                                            and rel_std_deviation < STD_DEV_THRESHOLD \
                                            and trend == 0:
                                        if t not in best_tickers_with_options:
                                            best_tickers_with_options.append(t)

                                        best_contracts_dict[cc_contract[i]] = [cc_contract[i], d, t, price, round(float(delta_price_premium), 2),
                                                                               round(float(spread_strike_price), 2), round(float(cc_strike[i]), 2),
                                                                                round(float(cc_bid[i] * 100), 2), cc_open_interest[i],
                                                                                cc_impl_volatility[i], ratio_bid_price, sector, industry,
                                                                                highest_price, avg_price, lowest_price, beta]
                                # stocks with uptrend
                                elif TREND == 1:
                                    if cc_bid[i] >= MIN_BID_PRICE \
                                            and cc_strike[i] > price \
                                            and price_vs_avgs == 1 \
                                            and rel_std_deviation < STD_DEV_THRESHOLD \
                                            and trend == 1:
                                        if t not in best_tickers_with_options:
                                            best_tickers_with_options.append(t)

                                        best_contracts_dict[cc_contract[i]] = [cc_contract[i], d, t, price, round(float(delta_price_premium), 2),
                                                                               round(float(spread_strike_price), 2), round(float(cc_strike[i]), 2),
                                                                                round(float(cc_bid[i] * 100), 2), cc_open_interest[i],
                                                                                cc_impl_volatility[i], ratio_bid_price, sector, industry,
                                                                                highest_price, avg_price, lowest_price, beta]

                                        print(f"Match: {cc_contract[i]}")
                                                                # stocks with uptrend
                                # no trend
                                elif TREND == -1:
                                    if cc_bid[i] >= MIN_BID_PRICE \
                                            and cc_strike[i] > price \
                                            and rel_std_deviation < STD_DEV_THRESHOLD:
                                        if t not in best_tickers_with_options:
                                            best_tickers_with_options.append(t)

                                        best_contracts_dict[cc_contract[i]] = [cc_contract[i], d, t, price, round(float(delta_price_premium), 2),
                                                                               round(float(spread_strike_price), 2), round(float(cc_strike[i]), 2),
                                                                                round(float(cc_bid[i] * 100), 2), cc_open_interest[i],
                                                                                cc_impl_volatility[i], ratio_bid_price, sector, industry,
                                                                                highest_price, avg_price, lowest_price, beta]

                                        print(f"Match: {cc_contract[i]}")

                    except Exception as e:
                        continue

                elif year == YEAR and month == MONTH and day in DAY and TYPE == 1:
                    pass
                elif year == YEAR and month == MONTH and day in DAY and TYPE == 2:
                    pass

        else:
            pass

elif STOCK_EXCHANGE == 2:
    pass

# sort by ratio_bid_strike
if STOCK_EXCHANGE in [0, 1]:
    sorted_best_contracts = sorted(best_contracts_dict.values(), key=lambda x: x[-7], reverse=True)
elif STOCK_EXCHANGE == 2:
    sorted_best_contracts = sorted(best_contracts_dict.values(), key=lambda x: x[-4], reverse=True)

# all tickers with active options
if WRITE_TICKERS_TO_FILE == 1 and SCOPE == 1 and STOCK_EXCHANGE == 0:
    functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_nyse.txt")
elif WRITE_TICKERS_TO_FILE == 1 and SCOPE == 1 and STOCK_EXCHANGE == 1:
    functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_nasdaq.txt")
elif WRITE_TICKERS_TO_FILE == 1 and SCOPE == 1 and STOCK_EXCHANGE == 2:
    functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_arca.txt")

# only the best cov calls
# contract, date, ticker, price, delta_price_premium, spread_strike_price, strike, bid, open_interest, imp_volatility, ratio_bid_price, sector, industry, highest_price, avg_price, lowest_price, beta
if STOCK_EXCHANGE == 0 and WRITE_TICKERS_TO_FILE == 1 and TYPE == 0:
    with open("/Users/madararubino/best_options/best_cov_calls_nyse.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "sector", "industry", "highest", "avg price", "lowest", "beta"])  # header row
        for row in sorted_best_contracts:
            writer.writerow([row[0], row[1], row[3], row[6], row[-10], row[-7], row[-6], row[-5], row[-4], row[-3], row[-2], row[-1]])

    with open("/Users/madararubino/option_screener_js/data/best_cov_calls_nyse.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "sector", "industry", "highest", "avg price", "lowest", "beta"])  # header row
        for row in sorted_best_contracts:
            writer.writerow([row[0], row[1], row[3], row[6], row[-10], row[-7], row[-6], row[-5], row[-4], row[-3], row[-2], row[-1]])
if STOCK_EXCHANGE == 1 and WRITE_TICKERS_TO_FILE == 1 and TYPE == 0:
    with open("/Users/madararubino/best_options/best_cov_calls_nasdaq.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "sector", "industry", "highest", "avg price", "lowest", "beta"])  # header row
        for row in sorted_best_contracts:
            writer.writerow([row[0], row[1], row[3], row[6], row[-10], row[-7], row[-6], row[-5], row[-4], row[-3], row[-2], row[-1]])

    with open("/Users/madararubino/option_screener_js/data/best_cov_calls_nasdaq.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["contract", "expiry_date", "current_price", "strike_price", "premium", "ratio", "sector", "industry", "highest", "avg price", "lowest", "beta"])  # header row
        for row in sorted_best_contracts:
            writer.writerow([row[0], row[1], row[3], row[6], row[-10], row[-7], row[-6], row[-5], row[-4], row[-3], row[-2], row[-1]])

end_time = time.time()
execution_time = end_time - start_time
print("--- EXECUTION TIME ---")
print(f"--> {execution_time:.3f} seconds")
print(f"--> {execution_time / 60:.2f} minutes")
