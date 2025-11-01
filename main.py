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

CALL = 0  # 0 call, 1 put
STOCK_EXCHANGE = 0
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]
SCOPE = 0  # 0 whole ticker list 1 only tickers with options
WRITE_TICKERS_TO_FILE = 0
MIN_BID_PRICE = 0.2
TREND = 0  # 0 no trend, 1 downtrend, 2 uptrend
HAVE_OPTIONS = 0  # 0 no active options, 1 with active options
STOCK_PRICE = 25

ticker = Assets.Equity("AAPL", "NASDAQ")
stock, price, options, sector, industry, beta, vol_aver_10days, vol_aver_3months = ticker.get_info()
print(options)
