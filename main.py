import sys
import time
import functions
import warnings
import pandas as pd
import Assets
import config
import spread_options
import covered_calls as cov_calls
import put_options as put_options
from concurrent.futures import ThreadPoolExecutor

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

max_stock_price = config.MAX_STOCK_PRICE
target_dates = config.TARGET_DATES
std_dev_threshold = config.STD_DEV_THRESHOLD
scope = config.SCOPE
write_tickers_to_file = config.WRITE_TICKERS_TO_FILE

option_type = config.OPTION_TYPE
exchanges = config.EXCHANGES
min_bid_price = config.MIN_BID_PRICE


def main(exchange_number: int = 0, option_type_input: int | None = None):
    stock_exchange = exchange_number
    option_no = option_type_input if option_type_input is not None else config.TYPE

    user_agent = functions.create_user_agent()
    CLEAR_CACHE = False
    if CLEAR_CACHE:
        user_agent.cache.clear()

    try:
        ftse_5d = functions.get_index_change_last5d("^FTSE", "5d")
        dow_jones_5d = functions.get_index_change_last5d("^DJI", "5d")
        ftse_1m = functions.get_index_change_last5d("^FTSE", "1mo")
        dow_jones_1m = functions.get_index_change_last5d("^DJI", "1mo")
        functions.get_vix()
        if ftse_5d > 0:
            print(f"|-- Index FTSE100 is {ftse_5d}% higher than the last 5 days --|")
        elif ftse_5d < 0:
            print(f"|-- WARNING: Index FTSE100 is {ftse_5d}% lower than the last 5 days --|")
        if dow_jones_5d > 0:
            print(f"|-- Index DOW JONES is {dow_jones_5d}% higher than the last 5 days --|")
        elif dow_jones_5d < 0:
            print(f"|-- WARNING: Index DOW JONES is {dow_jones_5d}% lower than the last 5 days --|")
        if ftse_1m < 0 and dow_jones_1m < 0:
            print(f"|-- WARNING: FTSE100 ({ftse_1m}) and DOW JONES ({dow_jones_1m}) are lower than 30 days ago!!! --|")
    except Exception:
        print("|-- WARNING: could not fetch market index data --|")

    print("|--------------------------------------------------------------------------|")

    match (stock_exchange, scope):
        case (0, 0):
            ticker_file = "/Users/madararubino/stocks_with_options_nyse.txt"
        case (1, 0):
            ticker_file = "/Users/madararubino/stocks_with_options_nasdaq.txt"
        case (2, 0):
            ticker_file = "/Users/madararubino/stocks_with_options_arca.txt"
        case (0, 1):
            ticker_file = "/Users/madararubino/shared_data/nyse_tickers_last.txt"
        case (1, 1):
            ticker_file = "/Users/madararubino/shared_data/nasdaq_tickers_last.txt"
        case (2, 1):
            ticker_file = "/Users/madararubino/shared_data/nyse_arca_tickers_last.txt"
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
        functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_nyse.txt")
    elif stock_exchange == 1 and scope == 1:
        functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_nasdaq.txt")
    elif stock_exchange == 2 and scope == 1:
        functions.write_tickers_to_file(tickers_with_options, "/Users/madararubino/stocks_with_options_arca.txt")

    # write NYSE covered calls
    if stock_exchange == 0 and option_no == 0:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_cov_calls_nyse.json", 0, all_best_contracts_sorted)
    # write NYSE put options
    if stock_exchange == 0 and option_no == 1:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_put_options_nyse.json", 0, all_best_contracts_sorted)
    # write NYSE spread options
    if stock_exchange == 0 and option_no == 2:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_spreads_nyse.json", 0, all_best_contracts_sorted)
    # write NASDAQ covered calls
    elif stock_exchange == 1 and option_no == 0:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_cov_calls_nasdaq.json", 1, all_best_contracts_sorted)
    # write NASDAQ put options
    elif stock_exchange == 1 and option_no == 1:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_put_options_nasdaq.json", 1, all_best_contracts_sorted)
    # write NASDAQ spread options
    elif stock_exchange == 1 and option_no == 2:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_spreads_nasdaq.json", 1, all_best_contracts_sorted)
    # write ARCA covered calls
    elif stock_exchange == 2 and option_no == 0:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_cov_calls_arca.json", 2, all_best_contracts_sorted)
    # write ARCA put options
    elif stock_exchange == 2 and option_no == 1:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_put_options_arca.json", 2, all_best_contracts_sorted)
    # write ARCA spread options
    elif stock_exchange == 2 and option_no == 2:
        functions.write_best_options_to_json(
            "/Users/madararubino/options-saas/shared/data/best_spreads_arca.json", 2, all_best_contracts_sorted)

    end_time = time.time()
    execution_time = end_time - start_time
    print("--- EXECUTION TIME ---")
    print(f"--> {execution_time:.3f} seconds")
    print(f"--> {execution_time / 60:.2f} minutes")


if __name__ == "__main__":
    def _ask(prompt: str, valid: tuple) -> int:
        while True:
            try:
                val = int(input(prompt))
                if val in valid:
                    return val
            except ValueError:
                pass
            print(f"Invalid input. Enter one of: {valid}")

    if len(sys.argv) > 1:
        main(int(sys.argv[1]))
    else:
        _opt = _ask("Option type  0=calls  1=puts  2=spreads\n>> ", (0, 1, 2))
        _exch = _ask("Exchange     0=NYSE   1=NASDAQ  2=ARCA\n>> ", (0, 1, 2))
        main(_exch, _opt)
