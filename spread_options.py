import Assets
from typing import Any
import config
import math
import functions
from covered_calls import scan_covered_calls as scan_spread_options


def scan_long_cov_calls(
        options,
        symbol,
        stock_price
):
    for d in options:
        """ It returns True if at least one long call has a consistent spread between price and strike"""
        has_long_calls = functions.is_at_least_3_months_after_today(d)
        if not has_long_calls:
            continue

        spreads = functions.get_alpaca_option_chain(symbol, d, "call")

        if spreads is None or spreads.empty:
            continue

        for row in spreads.itertuples(index=False):
            if row.strike >= stock_price:
                continue

            spread_strike_price = round(abs(row.strike - stock_price), 2)

            if spread_strike_price >= 6:
                return True

    return False


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
