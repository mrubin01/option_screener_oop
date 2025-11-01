import sys
import time
import functions
import warnings
import pandas as pd
import Assets


warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

user_agent = functions.create_user_agent()

# empty the cache only the first run of the day
CLEAR_CACHE = False
if CLEAR_CACHE:
    user_agent.cache.clear()

TYPE = 0  # 0 call, 1 put, 2 spread
STOCK_EXCHANGE = 1
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]
SCOPE = 0  # 0 only tickers with options, 1 whole ticker list
WRITE_TICKERS_TO_FILE = 0
MIN_BID_PRICE = 0.2
TREND = 2  # 0 no trend, 1 downtrend, 2 uptrend
HAVE_OPTIONS = 0  # 0 no active options, 1 with active options
MAX_STOCK_PRICE = 1000
YEAR, MONTH, DAY = 2025, 11, [21, 28]

ticker_list = ["AAPL", ""]
tickers_with_options = []

if STOCK_EXCHANGE in [0, 1]:
    for t in ticker_list:
        ticker = Assets.Equity(t, EXCHANGES[1])
        stock, price, options, sector, industry, beta, vol_aver_10days, vol_aver_3months = ticker.get_info()
        if len(options) > 0 and price <= MAX_STOCK_PRICE:
            if t not in tickers_with_options:
                tickers_with_options.append(t)

            price_data = ticker.get_high_low_price()
            lowest_price, highest_price, first_price, last_price = price_data[0], price_data[1], price_data[2], price_data[3]
            avg_price, avg_price_7d, avg_price_30d = price_data[4], price_data[5], price_data[6]




elif STOCK_EXCHANGE == 2:
    pass

