from datetime import date, timedelta


def _next_n_fridays(n: int) -> list[date]:
    today = date.today()
    days_until_friday = (4 - today.weekday()) % 7 or 7
    first = today + timedelta(days=days_until_friday)
    return [first + timedelta(weeks=i) for i in range(n)]


TARGET_DATES = [d.strftime("%Y-%m-%d") for d in _next_n_fridays(3)]

# global variables
TYPE = 0  # 0 call, 1 put, 2 spread
STD_DEV_THRESHOLD = 15
STRIKE_PRICE_THRESHOLD = 1.5  # overridden inside main() per exchange
SCOPE = 0  # 0 only tickers with options, 1 whole ticker list

OPTION_TYPE = ["Call", "Put", "Spread"]
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]

RISK_FREE_RATE = 3.86  # 1-month Treasury rate
OPTION_YIELD_THRESHOLD = 25

# Exchange-specific thresholds (computed inside main() from exchange_number)
NYSE_NASDAQ_MAX_STOCK_PRICE = 50
ARCA_MAX_STOCK_PRICE = 200
NYSE_NASDAQ_MIN_BID_PRICE = 0.2
ARCA_MIN_BID_PRICE = 0.5

# Spread-specific filters
SPREAD_MIN_EXPIRY_DATES = 10
SPREAD_MIN_ITM_DISTANCE = 6

if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
