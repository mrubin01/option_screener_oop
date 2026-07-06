from datetime import date, timedelta


def _next_n_fridays(n: int) -> list[date]:
    today = date.today()
    days_until_friday = (4 - today.weekday()) % 7 or 7
    first = today + timedelta(days=days_until_friday)
    return [first + timedelta(weeks=i) for i in range(n)]


TARGET_DATES = [d.strftime("%Y-%m-%d") for d in _next_n_fridays(3)]

# global variables
TYPE = 0  # 0 call, 1 put, 2 spread
STOCK_EXCHANGE = 0  # nyse, nasdaq, arca
STD_DEV_THRESHOLD = 15
if STOCK_EXCHANGE in [0, 1]:
    STRIKE_PRICE_THRESHOLD = 1.5
else:
    STRIKE_PRICE_THRESHOLD = 3
SCOPE = 0  # 0 only tickers with options, 1 whole ticker list
WRITE_TICKERS_TO_FILE = 1

OPTION_TYPE = ["Call", "Put", "Spread"]
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]
TREND_DOWN = -1
TREND_SIDEWAYS = 0
TREND_UP = 1

RISK_FREE_RATE = 3.86  # 1-month Treasury rate
OPTION_YIELD_THRESHOLD = 25

if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
