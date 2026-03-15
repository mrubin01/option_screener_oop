# global variables
TEST = False
TYPE = 0  # 0 call, 1 put, 2 spread
STOCK_EXCHANGE = 0  # nyse, nasdaq, arca
TREND = -1  # -1 no trend, 0 downtrend, 1 uptrend
if TYPE in [0, 1]:
    MAX_STOCK_PRICE = 500
else:
    MAX_STOCK_PRICE = 100
YEAR, MONTH, DAY = 2026, [3], [20]  # 2026, [2], [6, 13, 20, 27]  # 2025, [11], [14]  #
STD_DEV_THRESHOLD = 50
SCOPE = 0  # 0 only tickers with options, 1 whole ticker list
WRITE_TICKERS_TO_FILE = 1

OPTION_TYPE = ["Call", "Put", "Spread"]
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]
MIN_BID_PRICE = 0.1
TREND_TYPE = ["downtrend", "uptrend", "no trend"]
HAVE_OPTIONS = 0  # 0 no active options, 1 with active options


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
