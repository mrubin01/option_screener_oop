import os
import sys
import time
import functions
import warnings
import pandas as pd
from pathlib import Path
import Assets
import config
import spread_options
import covered_calls as cov_calls
import put_options as put_options
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = Path(__file__).parent
TICKERS_DIR = BASE_DIR / "tickers"

_output_dir = os.getenv("OUTPUT_DIR")
if not _output_dir:
    raise RuntimeError("OUTPUT_DIR must be set in .env")
OUTPUT_DIR = Path(_output_dir)

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

target_dates = config.TARGET_DATES
std_dev_threshold = config.STD_DEV_THRESHOLD
scope = config.SCOPE
write_tickers_to_file = config.WRITE_TICKERS_TO_FILE

option_type = config.OPTION_TYPE
exchanges = config.EXCHANGES

# Ordered list of (exchange, option_type) for a full automated run
SCANS = [
    (0, 0),  # calls  NYSE
    (1, 1),  # puts   NASDAQ
    (2, 2),  # spread ARCA
    (1, 0),  # calls  NASDAQ
    (2, 1),  # puts   ARCA
    (0, 2),  # spread NYSE
    (2, 0),  # calls  ARCA
    (0, 1),  # puts   NYSE
    (1, 2),  # spread NASDAQ
]


def main(exchange_number: int = 0, option_type_input: int | None = None):
    stock_exchange = exchange_number
    option_no = option_type_input if option_type_input is not None else config.TYPE

    # Exchange-specific thresholds — must be derived from the actual exchange
    # passed at call time, not from config.STOCK_EXCHANGE set at load time.
    if stock_exchange in [0, 1]:
        max_stock_price = 50
        min_bid_price = 0.2
        config.STRIKE_PRICE_THRESHOLD = 1.5
    else:
        max_stock_price = 200
        min_bid_price = 0.5
        config.STRIKE_PRICE_THRESHOLD = 3

    print("|--------------------------------------------------------------------------|")

    match (stock_exchange, scope):
        case (0, 0):
            ticker_file = TICKERS_DIR / "nyse_options.txt"
        case (1, 0):
            ticker_file = TICKERS_DIR / "nasdaq_options.txt"
        case (2, 0):
            ticker_file = TICKERS_DIR / "arca_options.txt"
        case (0, 1):
            ticker_file = TICKERS_DIR / "nyse_full.txt"
        case (1, 1):
            ticker_file = TICKERS_DIR / "nasdaq_full.txt"
        case (2, 1):
            ticker_file = TICKERS_DIR / "arca_full.txt"
        case _:
            print("Wrong values!")
            sys.exit()

    with open(ticker_file, "r") as my_file:
        data = my_file.read()
    data_into_list = data.replace('\n', ', ').split(", ")
    ticker_list = list(filter(None, data_into_list))
    # ticker_list = ["XBI", "UPRO", "GDXJ"]

    start_time = time.time()
    print(f"|-- Scanning {option_type[option_no]} options in {exchanges[stock_exchange]} --|")
    print()

    all_best_contracts = []
    tickers_with_options = []

    if stock_exchange in [0, 1]:

        def _process_equity_ticker(t: str) -> tuple[list[dict], bool]:
            ticker = Assets.Equity(t, exchanges[stock_exchange])
            ticker_data = ticker.get_info()
            if not ticker_data:
                return [], False

            price = float(ticker_data["price"])
            options = ticker_data["options"]
            sector = functions.normalize_nullable_fields(ticker_data["sector"])
            industry = functions.normalize_nullable_fields(ticker_data["industry"])
            beta = functions.normalize_nullable_float(ticker_data["beta"])

            if price > max_stock_price:
                return [], False

            price_data = ticker.get_price_stats()
            if not price_data:
                return [], False

            lowest_price = price_data["low"]
            highest_price = price_data["high"]
            avg_price = price_data["avg_price"]
            avg_price_7d = price_data["avg_price_7d"]
            avg_price_30d = price_data["avg_price_30d"]
            trend = price_data["price_trend"]
            rel_std_deviation = price_data["rel_sd"]

            if rel_std_deviation > std_dev_threshold:
                return [], False

            if len(options) == 0:
                return [], False

            has_long_itm_options = False
            if option_no == 2:
                has_long_itm_options = spread_options.scan_long_cov_calls(options, t, price)

            matched = []
            for d in options:
                if d not in target_dates:
                    continue
                try:
                    if option_no == 0:
                        best_contracts = cov_calls.scan_covered_calls(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            lowest_price, highest_price, avg_price, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            sector=sector, industry=industry, beta=beta)
                    elif option_no == 1:
                        best_contracts = put_options.scan_put_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            lowest_price, highest_price, avg_price, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            sector=sector, industry=industry, beta=beta)
                    elif option_no == 2 and len(options) > 10 and has_long_itm_options:
                        best_contracts = spread_options.scan_spread_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            lowest_price, highest_price, avg_price, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            sector=sector, industry=industry, beta=beta)
                    else:
                        best_contracts = []
                except Exception:
                    continue
                matched.extend(best_contracts)

            return matched, True

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(_process_equity_ticker, ticker_list))

        for t, (contracts, had_options) in zip(ticker_list, results):
            if had_options:
                tickers_with_options.append(t)
            all_best_contracts.extend(contracts)

    elif stock_exchange == 2:

        def _process_etf_ticker(t: str) -> tuple[list[dict], bool]:
            ticker = Assets.ETF(t, exchanges[stock_exchange])
            ticker_data = ticker.get_info_etf()
            if not ticker_data:
                return [], False

            price = float(ticker_data["price"])
            options = ticker_data["options"]

            if price > max_stock_price:
                return [], False

            price_data = ticker.get_price_stats()
            if not price_data:
                return [], False

            lowest_price = price_data["low"]
            highest_price = price_data["high"]
            avg_price = price_data["avg_price"]
            avg_price_7d = price_data["avg_price_7d"]
            avg_price_30d = price_data["avg_price_30d"]
            trend = price_data["price_trend"]
            rel_std_deviation = price_data["rel_sd"]

            if rel_std_deviation > std_dev_threshold:
                return [], False

            if len(options) == 0:
                return [], False

            matched = []
            for d in options:
                if d not in target_dates:
                    continue
                try:
                    if option_no == 0:
                        best_contracts = cov_calls.scan_covered_calls(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            lowest_price, highest_price, avg_price, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation)
                    elif option_no == 1:
                        best_contracts = put_options.scan_put_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            lowest_price, highest_price, avg_price, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation)
                    elif option_no == 2 and len(options) > 10:
                        best_contracts = spread_options.scan_spread_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            lowest_price, highest_price, avg_price, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation)
                    else:
                        best_contracts = []
                except Exception:
                    continue
                matched.extend(best_contracts)

            return matched, True

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(_process_etf_ticker, ticker_list))

        for t, (contracts, had_options) in zip(ticker_list, results):
            if had_options:
                tickers_with_options.append(t)
            all_best_contracts.extend(contracts)

    all_best_contracts_sorted = sorted(all_best_contracts, key=lambda x: x["option_yield"], reverse=True)
    print(f"Tot. number of contracts: {len(all_best_contracts_sorted)}")
    print()

    # write list of tickers with options
    if stock_exchange == 0 and scope == 1:
        functions.write_tickers_to_file(tickers_with_options, str(TICKERS_DIR / "nyse_options.txt"))
    elif stock_exchange == 1 and scope == 1:
        functions.write_tickers_to_file(tickers_with_options, str(TICKERS_DIR / "nasdaq_options.txt"))
    elif stock_exchange == 2 and scope == 1:
        functions.write_tickers_to_file(tickers_with_options, str(TICKERS_DIR / "arca_options.txt"))

    # write NYSE covered calls
    if stock_exchange == 0 and option_no == 0:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_cov_calls_nyse.json", 0, all_best_contracts_sorted)
    # write NYSE put options
    if stock_exchange == 0 and option_no == 1:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_put_options_nyse.json", 0, all_best_contracts_sorted)
    # write NYSE spread options
    if stock_exchange == 0 and option_no == 2:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_spreads_nyse.json", 0, all_best_contracts_sorted)
    # write NASDAQ covered calls
    elif stock_exchange == 1 and option_no == 0:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_cov_calls_nasdaq.json", 1, all_best_contracts_sorted)
    # write NASDAQ put options
    elif stock_exchange == 1 and option_no == 1:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_put_options_nasdaq.json", 1, all_best_contracts_sorted)
    # write NASDAQ spread options
    elif stock_exchange == 1 and option_no == 2:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_spreads_nasdaq.json", 1, all_best_contracts_sorted)
    # write ARCA covered calls
    elif stock_exchange == 2 and option_no == 0:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_cov_calls_arca.json", 2, all_best_contracts_sorted)
    # write ARCA put options
    elif stock_exchange == 2 and option_no == 1:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_put_options_arca.json", 2, all_best_contracts_sorted)
    # write ARCA spread options
    elif stock_exchange == 2 and option_no == 2:
        functions.write_best_options_to_json(
            OUTPUT_DIR / "best_spreads_arca.json", 2, all_best_contracts_sorted)

    end_time = time.time()
    execution_time = end_time - start_time
    print("--- EXECUTION TIME ---")
    print(f"--> {execution_time:.3f} seconds")
    print(f"--> {execution_time / 60:.2f} minutes")


if __name__ == "__main__":
    total_start = time.time()
    for i, (exch, opt) in enumerate(SCANS, 1):
        print(f"\n{'='*74}")
        print(f"  Scan {i}/{len(SCANS)}: {option_type[opt]} — {exchanges[exch]}")
        print(f"{'='*74}")
        main(exch, opt)
    total_elapsed = time.time() - total_start
    print(f"\n{'='*74}")
    print(f"  All {len(SCANS)} scans complete — {total_elapsed/60:.1f} min total")
    print(f"{'='*74}")
