# global variables
TEST = False
TYPE = 2  # 0 call, 1 put, 2 spread
STOCK_EXCHANGE = 0  # nyse, nasdaq, arca
if STOCK_EXCHANGE in [0, 1]:
    MAX_STOCK_PRICE = 50
else:
    MAX_STOCK_PRICE = 200
YEAR, MONTH, DAY = 2026, [6, 7], [2, 26]  # 2026, [2], [6, 13, 20, 27]  # 2025, [11], [14]  #
STD_DEV_THRESHOLD = 15
if STOCK_EXCHANGE in [0, 1]:
    STRIKE_PRICE_THRESHOLD = 1.5
else:
    STRIKE_PRICE_THRESHOLD = 3
SCOPE = 0  # 0 only tickers with options, 1 whole ticker list
WRITE_TICKERS_TO_FILE = 1

OPTION_TYPE = ["Call", "Put", "Spread"]
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]
if STOCK_EXCHANGE in [0, 1]:
    MIN_BID_PRICE = 0.2
else:
    MIN_BID_PRICE = 0.5
HAVE_OPTIONS = 0  # 0 no active options, 1 with active options

TREND_DOWN = -1
TREND_SIDEWAYS = 0
TREND_UP = 1

RISK_FREE_RATE = 3.86  # 1-month Treasury rate
OPTION_YIELD_THRESHOLD = 25

if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
