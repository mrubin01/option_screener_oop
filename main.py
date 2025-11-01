import sys
import time
import functions
import warnings
import pandas as pd


warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

user_agent = functions.create_user_agent()

# empty the cache only the first run of the day
CLEAR_CACHE = False
if CLEAR_CACHE:
    user_agent.cache.clear()

CALL = 1  # 1 call, 2 put
STOCK_EXCHANGE = 2  # 1 NYSE, 2 NASDAQ, 3 ARCA
SCOPE = 1  # 1 whole ticker list 2 only tickers with options
WRITE_TICKERS_TO_FILE = 0
MIN_BID_PRICE = 0.2
TREND = -1  # -1 no trend, 1 downtrend, 2 uptrend
HAVE_OPTIONS = 0  # 0 no active options, 1 with active options
STOCK_PRICE = 25


