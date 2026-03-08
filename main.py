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
# ticker_list = list(filter(None, data_into_list))
# ticker_list = ["TNA", "BOIL", "KOLD", "SOXL", "IWM", "GDX", "SILJ"]
ticker_list = ["AAPL"]

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
            stock, price, options, sector, industry, beta, vol_aver_10days, vol_aver_3months = ticker.get_info()
            if len(options) > 0 and price <= max_stock_price:
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

                    if year == i_year and month in l_month and day in l_day and option_no == 0:
                        # covered calls
                        try:
                            best_contracts = cov_calls.run(ticker, d, min_bid_price, rel_std_deviation, std_dev_threshold)
                        except Exception as e:
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

