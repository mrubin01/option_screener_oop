import sys
import time
import functions
import warnings
import pandas as pd
from datetime import datetime
import csv
import Assets
import config
import spread_options_short_calls
import covered_calls as cov_calls

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

user_agent = functions.create_user_agent()

# empty the cache only the first run of the day
CLEAR_CACHE = False
if CLEAR_CACHE:
    user_agent.cache.clear()

# Market indexes
ftse_5d = functions.get_index_change_last5d("^FTSE", "5d")
dow_jones_5d = functions.get_index_change_last5d("^DJI", "5d")
ftse_1m = functions.get_index_change_last5d("^FTSE", "1mo")
dow_jones_1m = functions.get_index_change_last5d("^DJI", "1mo")
functions.get_vix()
if ftse_5d > 0:
    print(f"|-- Index FTSE100 is {ftse_5d}% higher than the last 5 days --|")
elif ftse_5d < 0:
    print(f"|-- WARNING: Index FTSE100 is {ftse_5d}% lower than the last 5 days --|")
if dow_jones_5d > 0:
    print(f"|-- Index DOW JONES is {dow_jones_5d}% higher than the last 5 days --|")
elif dow_jones_5d < 0:
    print(f"|-- WARNING: Index DOW JONES is {dow_jones_5d}% lower than the last 5 days --|")

if ftse_1m < 0 and dow_jones_1m:
    print(f"|-- WARNING: FTSE100 ({ftse_1m}) and DOW JONES ({dow_jones_1m}) are lower than 30 days ago!!! --|")

print("|--------------------------------------------------------------------------|")

test = config.TEST
option_no = config.TYPE  # 0 call, 1 put, 2 spread
stock_exchange = config.STOCK_EXCHANGE
trend_no = config.TREND
max_stock_price = config.MAX_STOCK_PRICE
i_year, l_month, l_day = config.YEAR, config.MONTH, config.DAY
std_dev_threshold = config.STD_DEV_THRESHOLD
scope = config.SCOPE
write_tickers_to_file = config.WRITE_TICKERS_TO_FILE

option_type = config.OPTION_TYPE
exchanges = config.EXCHANGES
min_bid_price = config.MIN_BID_PRICE
trend_type = config.TREND_TYPE
have_options = config.HAVE_OPTIONS


match (stock_exchange, scope):
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
# ticker_list = ["TNA", "BOIL", "KOLD", "SOXL", "IWM", "GDX", "SILJ"]
# ticker_list = ["AAPL"]

tickers_with_options = []

stock_exchange = config.STOCK_EXCHANGE


def main():
    best_contracts = []
    start_time = time.time()
    if stock_exchange in [0, 1] and not test:
        print(f"|-- Scanning {option_type[option_no]} options in {exchanges[stock_exchange]} --|")
        print()
        for t in ticker_list:
            ticker = Assets.Equity(t, exchanges[stock_exchange])

            print(f"Scanning stock {t}...")

            ticker_data = ticker.get_info()
            if not ticker_data:
                continue

            stock = ticker_data["stock"]
            price = float(ticker_data["price"])
            options = ticker_data["options"]
            sector = ticker_data["sector"]
            industry = ticker_data["industry"]
            beta = float(ticker_data["beta"])
            # vol_aver_10days = ticker_data["vol_aver_10days"]
            # vol_aver_3months = ticker_data["vol_aver_3months"]

            price_data = ticker.get_price_stats()
            if not price_data:
                return []

            lowest_price = price_data["low"]
            highest_price = price_data["high"]
            # first_price = price_data["first_price"]
            # last_price = price_data["last_price"]
            avg_price = price_data["avg_price"]
            avg_price_7d = price_data["avg_price_7d"]
            avg_price_30d = price_data["avg_price_30d"]
            trend = price_data["price_trend"]
            # abs_std_deviation = price_data["abs_sd"]
            rel_std_deviation = price_data["rel_sd"]

            if rel_std_deviation > std_dev_threshold:
                continue

            if len(options) > 0 and price <= max_stock_price:
                if t not in tickers_with_options:
                    tickers_with_options.append(t)

                for d in options:
                    new_date = datetime.strptime(d, "%Y-%m-%d")
                    day = new_date.day
                    month = new_date.month
                    year = new_date.year

                    if year == i_year and month in l_month and day in l_day and option_no == 0:
                        # covered calls
                        try:
                            best_contracts = cov_calls.run(ticker,
                                                           d,
                                                           min_bid_price,
                                                           std_dev_threshold,
                                                           stock,
                                                           price,
                                                           sector,
                                                           industry,
                                                           beta,
                                                           lowest_price,
                                                           highest_price,
                                                           avg_price,
                                                           avg_price_7d,
                                                           avg_price_30d,
                                                           trend,
                                                           rel_std_deviation)
                        except Exception as e:
                            continue

                        if len(best_contracts) == 0:
                            continue

                    # put options
                    elif year == i_year and month in l_month and day in l_day and option_no == 1:
                        pass

                    # spread options
                    elif year == i_year and month in l_month and day in l_day and option_no == 2:
                        pass
    print(best_contracts)


if __name__ == "__main__":
    main()

