import sys
import time
import math
import functions
import warnings
import pandas as pd
from datetime import datetime
import Assets
import config

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)


def run(year_short: int, month_short: list, day_short: list, exchange: int, tickers: list):
    start_time = time.time()

    if exchange != 2:
        print("Only ARCA is accepted!")
        sys.exit()

    if not isinstance(year_short, int) or \
            not isinstance(month_short, list) or \
            not isinstance(day_short, list) or \
            not isinstance(tickers, list):
        print("Something is wrong with the parameters!")
        sys.exit()

    print("|-- Scanning the best short covered call... --|")
    print()

    tickers_with_options = []
    all_best_contracts = []

    for t in tickers:
        print(t)
        ticker = Assets.ETF(t, config.EXCHANGES[exchange])

        ticker_data = ticker.get_info_etf()
        if not ticker_data:
            continue

        stock = ticker_data["stock"]
        price = float(ticker_data["price"])
        options = ticker_data["options"]

        if len(options) < 10 or price > config.MAX_STOCK_PRICE:
            continue

        if t not in tickers_with_options:
            tickers_with_options.append(t)

        price_data = ticker.get_price_stats_etf()
        if not price_data:
            continue

        lowest_price = price_data["low"]
        highest_price = price_data["high"]
        avg_price = price_data["avg_price"]
        avg_price_7d = price_data["avg_price_7d"]
        avg_price_30d = price_data["avg_price_30d"]
        trend = price_data["price_trend"]
        rel_std_deviation = price_data["rel_sd"]

        if rel_std_deviation > config.STD_DEV_THRESHOLD:
            continue

        main_trend = functions.compute_main_trend(price, avg_price, avg_price_7d, avg_price_30d, trend)

        for d in options:
            new_date = datetime.strptime(d, "%Y-%m-%d")
            if not (new_date.year == year_short and new_date.month in month_short and new_date.day in day_short):
                continue

            try:
                cc = stock.option_chain(d).calls
            except Exception:
                continue

            if cc is None or cc.empty:
                continue

            dte = functions.days_to_expiration(d)

            for row in cc.itertuples(index=False):
                if isinstance(row.bid, float) and math.isnan(row.bid):
                    continue

                spread_strike_price = round(row.strike - price, 2)

                if spread_strike_price < 1.5 or row.bid < config.MIN_BID_PRICE:
                    continue

                spread_bid_ask = round(row.ask - row.bid, 2)
                delta_price_premium = round(row.strike - price + row.bid, 2)
                break_even = round(price - row.bid, 2)
                moneyness = round(((row.strike - price) / price) * 100, 2)
                option_yield = round((row.bid / price) * 100, 2)

                if option_yield >= config.OPTION_YIELD_THRESHOLD:
                    continue

                annualized_option_yield = round(option_yield * (365 / dte), 2)
                tot_return = round(((row.strike - price + row.bid) / price) * 100, 2)
                sigma_distance = functions.sigma_distance_to_strike(
                    price, float(row.strike), float(row.impliedVolatility), dte
                )
                est_delta = functions.estimate_delta(
                    "cc", price, row.strike, dte, config.RISK_FREE_RATE, row.impliedVolatility
                )

                contract = {
                    "ticker": t,
                    "exchange": exchange,
                    "contract": row.contractSymbol,
                    "expiry_date": d,
                    "days_to_expiration": dte,
                    "current_price": price,
                    "coeff_variation": rel_std_deviation,
                    "max_profit": round(float(delta_price_premium), 2),
                    "max_profit_per_contract": round(float(delta_price_premium * 100), 2),
                    "otm": round(float(spread_strike_price), 2),
                    "strike_price": round(float(row.strike), 2),
                    "moneyness": round(moneyness, 2),
                    "sigma_distance": round(sigma_distance, 2),
                    "bid_per_share": round(float(row.bid), 2),
                    "premium_per_contract": round(float(row.bid * 100), 2),
                    "spread_bid_ask": round(float(spread_bid_ask), 2),
                    "break_even": break_even,
                    "open_interest": int(row.openInterest) if row.openInterest is not None and not (isinstance(row.openInterest, float) and math.isnan(row.openInterest)) else 0,
                    "impl_volatility": round(float(row.impliedVolatility * 100), 2),
                    "option_yield": option_yield,
                    "roc": annualized_option_yield,
                    "tot_return": tot_return,
                    "delta": est_delta,
                    "highest_price": highest_price,
                    "avg_price": avg_price,
                    "lowest_price": lowest_price,
                    "main_trend": main_trend,
                }

                all_best_contracts.append(contract)
                print(f"Match: {row.contractSymbol}; strike {row.strike} > price {price}; bid {row.bid}")

    sorted_best_contracts = sorted(all_best_contracts, key=lambda x: x["option_yield"], reverse=True)
    print(f"Tot. number of contracts: {len(sorted_best_contracts)}")

    if config.WRITE_TICKERS_TO_FILE == 1 and config.SCOPE == 1:
        functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_arca.txt")

    functions.write_best_options_to_json(
        "/Users/madararubino/options-saas/shared/data/best_spreads_short_calls_arca.json",
        exchange,
        sorted_best_contracts,
    )

    end_time = time.time()
    execution_time = end_time - start_time
    print("--- EXECUTION TIME ---")
    print(f"--> {execution_time:.3f} seconds")
    print(f"--> {execution_time / 60:.2f} minutes")


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
