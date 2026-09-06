import concurrent.futures
import os
import sys
import time
import functions
import warnings
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import date as _date, datetime, timedelta
import Assets
import alpaca_client
import config
import spread_options
import covered_calls as cov_calls
import put_options as put_options
import long_calls
import long_puts
from concurrent.futures import ThreadPoolExecutor
from alpaca.data.requests import StockLatestTradeRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

STOCK_OPTIONS_DIR = Path("~/shared_data/stock_options").expanduser()

_output_dir = os.getenv("OUTPUT_DIR")
if not _output_dir:
    raise RuntimeError("OUTPUT_DIR must be set in .env")
OUTPUT_DIR = Path(_output_dir)


warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

target_dates = config.TARGET_DATES
std_dev_threshold = config.STD_DEV_THRESHOLD

option_type = config.OPTION_TYPE
exchanges = config.EXCHANGES

# 3 scans: one per exchange, all 4 strategies processed in a single ticker pass (type 7)
SCANS = [
    (0, 7), (1, 7), (2, 7),  # NYSE / NASDAQ / ARCA — covered calls + long calls + puts + long puts
]

_YF_TIMEOUT = 15
_PREFETCH_TTL = 1800  # 30 minutes

# Cache: exchange_number -> (timestamp, trades_dict, bars_dict)
_prefetch_cache: dict[int, tuple[float, dict, dict]] = {}


def _yf_call(fn, timeout=_YF_TIMEOUT):
    alpaca_client._yf_limiter.acquire()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(fn).result(timeout=timeout)


def _compute_price_stats_from_bars(symbol: str, bar_list) -> dict:
    """Compute the same stats as Asset.get_price_stats() from pre-fetched bar data."""
    try:
        close_prices = pd.Series(
            [b.close for b in bar_list],
            index=[b.timestamp.date() for b in bar_list],
            dtype=float,
        ).dropna()
        if close_prices.empty:
            return {}
        high_prices = pd.Series([b.high for b in bar_list], dtype=float)
        low_prices = pd.Series([b.low for b in bar_list], dtype=float)
        abs_sd, rel_sd = functions.get_std_dev(symbol, close_prices)
        return {
            "ma_20": round(float(close_prices.tail(20).mean()), 2),
            "ma_50": round(float(close_prices.tail(50).mean()), 2),
            "high_90d": round(float(high_prices.max()), 2),
            "low_90d": round(float(low_prices.min()), 2),
            "first_price": round(float(close_prices.iloc[0]), 2),
            "last_price": round(float(close_prices.iloc[-1]), 2),
            "avg_price": round(float(close_prices.mean()), 2),
            "avg_price_7d": round(float(close_prices.tail(7).mean()), 2),
            "avg_price_30d": round(float(close_prices.tail(30).mean()), 2),
            "price_trend": functions.get_price_trend(close_prices.tail(30)),
            "abs_sd": abs_sd,
            "rel_sd": rel_sd,
            "hv": functions.compute_hv(close_prices),
        }
    except Exception:
        return {}


def _prefetch_stock_data(ticker_list: list[str], max_stock_price: float, exchange_number: int = -1) -> tuple[dict, dict]:
    """
    Bulk-fetch latest trades and 90-day bars for all tickers in two Alpaca calls.
    Returns (trades_dict, bars_dict) keyed by symbol.
    Tickers above max_stock_price are excluded from the bars fetch.
    Results are cached per exchange for 30 minutes to avoid redundant API calls.
    """
    # Check cache
    cached = _prefetch_cache.get(exchange_number)
    if cached is not None:
        ts, trades_c, bars_c = cached
        age = time.time() - ts
        if age < _PREFETCH_TTL:
            mins = int(age // 60)
            secs = int(age % 60)
            print(f"|-- Using cached prefetch data ({mins}m {secs}s old, TTL 30 min) --|")
            return trades_c, bars_c

    # 1. Bulk latest trades — filter out tickers with characters Alpaca rejects (e.g. BF/A)
    clean_list = [t for t in ticker_list if "/" not in t]
    skipped = len(ticker_list) - len(clean_list)
    if skipped:
        print(f"|-- Skipping {skipped} tickers with unsupported characters (e.g. BF/A) --|")
    print(f"|-- Prefetching latest trades for {len(clean_list)} tickers... --|")
    try:
        trade_req = StockLatestTradeRequest(symbol_or_symbols=clean_list)
        trades = alpaca_client.get_latest_trades(trade_req, timeout=alpaca_client._BULK_TIMEOUT)
    except Exception as e:
        err = str(e)
        if "invalid symbol:" in err:
            bad = err.split("invalid symbol:")[-1].strip().strip('"').strip("}")
            clean_list = [t for t in clean_list if t != bad]
            print(f"|-- Retrying without bad symbol '{bad}' ({len(clean_list)} tickers)... --|")
            try:
                trade_req = StockLatestTradeRequest(symbol_or_symbols=clean_list)
                trades = alpaca_client.get_latest_trades(trade_req, timeout=alpaca_client._BULK_TIMEOUT)
            except Exception as e2:
                print(f"|-- Trade prefetch failed ({e2}); will skip tickers without trade data --|")
                trades = {}
        else:
            print(f"|-- Trade prefetch failed ({e}); will skip tickers without trade data --|")
            trades = {}

    # 2. Filter by price to avoid fetching bars for tickers we'll skip anyway
    eligible = [t for t in ticker_list if t in trades and float(trades[t].price) <= max_stock_price]
    print(f"|-- {len(eligible)}/{len(ticker_list)} tickers within price cap; prefetching 90-day bars... --|")

    # 3. Bulk 90-day bars
    bars: dict = {}
    if eligible:
        try:
            bars_req = StockBarsRequest(
                symbol_or_symbols=eligible,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=90),
            )
            resp = alpaca_client.get_stock_bars(bars_req, timeout=alpaca_client._BULK_TIMEOUT)
            bars = resp.data if resp and resp.data else {}
        except Exception as e:
            print(f"|-- Bars prefetch failed ({e}); tickers without cached bars will be skipped --|")

    print(f"|-- Prefetch complete: {len(trades)} trades, {len(bars)} bar sets --|")
    _prefetch_cache[exchange_number] = (time.time(), trades, bars)
    return trades, bars


def _read_tickers_csv(csv_path: Path) -> tuple[list[str], dict[str, dict]]:
    """Read exchange CSV and return ticker list + fundamentals dict.

    Supports two formats:
      - 4-col (legacy):  ticker,sector,industry...,beta
      - 6-col (current): ticker,sector,industry...,beta,ex_dividend_date,earnings_date
    Industry may contain commas; the two trailing date columns are fixed-position.
    """
    ticker_list = []
    fundamentals = {}
    with open(csv_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            ticker = parts[0].strip()
            if not ticker:
                continue
            ticker_list.append(ticker)
            if len(parts) >= 6:
                # 6-col format: last 3 fixed fields are beta, ex_dividend_date, earnings_date
                sector = functions.normalize_nullable_fields(parts[1].strip() or None)
                industry = functions.normalize_nullable_fields(",".join(parts[2:-3]).strip() or None)
                try:
                    beta = float(parts[-3].strip())
                except ValueError:
                    beta = None
                ex_dividend_date = parts[-2].strip() or None
                earnings_date = parts[-1].strip() or None
            elif len(parts) >= 4:
                sector = functions.normalize_nullable_fields(parts[1].strip() or None)
                industry = functions.normalize_nullable_fields(",".join(parts[2:-1]).strip() or None)
                try:
                    beta = float(parts[-1].strip())
                except ValueError:
                    beta = None
                ex_dividend_date = None
                earnings_date = None
            else:
                sector = None
                industry = None
                beta = None
                ex_dividend_date = None
                earnings_date = None
            fundamentals[ticker] = {
                "sector": sector, "industry": industry, "beta": beta,
                "ex_dividend_date": ex_dividend_date, "earnings_date": earnings_date,
            }
    return ticker_list, fundamentals


def main(exchange_number: int = 0, option_type_input: int | None = None):
    stock_exchange = exchange_number
    option_no = option_type_input if option_type_input is not None else config.TYPE

    # Exchange-specific thresholds — must be derived from the actual exchange
    # passed at call time, not from config.STOCK_EXCHANGE set at load time.
    if stock_exchange in [0, 1]:
        max_stock_price = config.NYSE_NASDAQ_MAX_STOCK_PRICE
        min_bid_price = config.NYSE_NASDAQ_MIN_BID_PRICE
    else:
        max_stock_price = config.ARCA_MAX_STOCK_PRICE
        min_bid_price = config.ARCA_MIN_BID_PRICE

    print("|--------------------------------------------------------------------------|")

    if stock_exchange == 0:
        csv_file = STOCK_OPTIONS_DIR / "stocks_with_options_nyse.csv"
    elif stock_exchange == 1:
        csv_file = STOCK_OPTIONS_DIR / "stocks_with_options_nasdaq.csv"
    elif stock_exchange == 2:
        csv_file = STOCK_OPTIONS_DIR / "stocks_with_options_arca.csv"
    else:
        print("Wrong exchange number!")
        sys.exit()

    ticker_list, ticker_fundamentals = _read_tickers_csv(csv_file)
    print(f"|-- Metadata loaded: {len(ticker_list)} tickers from CSV --|")

    start_time = time.time()
    print(f"|-- Scanning {option_type[option_no]} options in {exchanges[stock_exchange]} --|")
    print()

    all_selling_contracts = []
    all_buying_contracts = []
    all_cov_calls: list[dict] = []
    all_long_calls: list[dict] = []
    all_put_options: list[dict] = []
    all_long_puts: list[dict] = []

    all_dates = sorted(set(target_dates) | set(config.LONG_TARGET_DATES))

    # Bulk prefetch: replaces per-ticker StockLatestTradeRequest + StockBarsRequest calls
    prefetched_trades, prefetched_bars = _prefetch_stock_data(ticker_list, max_stock_price, exchange_number=stock_exchange)

    if stock_exchange in [0, 1]:

        def _process_equity_ticker_combined(t: str) -> tuple[list, list, list, list]:
            """Process one equity ticker using pre-fetched price/bars data."""
            # Price from bulk prefetch
            trade = prefetched_trades.get(t)
            if not trade:
                return [], [], [], []
            price = float(trade.price)
            if price > max_stock_price:
                return [], [], [], []

            # Price stats from bulk prefetch
            bar_list = prefetched_bars.get(t)
            if not bar_list:
                return [], [], [], []
            price_data = _compute_price_stats_from_bars(t, bar_list)
            if not price_data:
                return [], [], [], []

            # Options expiry list from yfinance (can't be batched)
            try:
                stock = yf.Ticker(t)
                options = _yf_call(lambda: stock.options)
                if not options:
                    return [], [], [], []
            except Exception:
                return [], [], [], []

            # Fundamentals from CSV
            fund = ticker_fundamentals.get(t, {})
            _today = _date.today()
            sector = fund.get("sector")
            industry = fund.get("industry")
            beta = fund.get("beta")

            ex_dividend_date = fund.get("ex_dividend_date") or None
            if ex_dividend_date:
                try:
                    ex_dividend_date = ex_dividend_date if _date.fromisoformat(ex_dividend_date) >= _today else None
                except ValueError:
                    ex_dividend_date = None

            earnings_date = fund.get("earnings_date") or None
            if earnings_date:
                try:
                    earnings_date = earnings_date if _date.fromisoformat(earnings_date) >= _today else None
                except ValueError:
                    earnings_date = None

            ticker = Assets.Equity(t, exchanges[stock_exchange])

            high_90d = price_data["high_90d"]
            low_90d = price_data["low_90d"]
            ma_20 = price_data["ma_20"]
            ma_50 = price_data["ma_50"]
            avg_price = price_data["avg_price"]
            avg_price_7d = price_data["avg_price_7d"]
            avg_price_30d = price_data["avg_price_30d"]
            trend = price_data["price_trend"]
            rel_std_deviation = price_data["rel_sd"]
            hv = price_data.get("hv", 0.0)

            too_volatile_for_selling = rel_std_deviation > std_dev_threshold

            if len(options) == 0:
                return [], [], [], []

            earnings_dt = None
            if earnings_date:
                try:
                    earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d").date()
                except ValueError:
                    pass
            ex_div_dt = None
            if ex_dividend_date:
                try:
                    ex_div_dt = datetime.strptime(ex_dividend_date, "%Y-%m-%d").date()
                except ValueError:
                    pass

            cc_out, lc_out, po_out, lp_out = [], [], [], []

            # One Alpaca call for the full chain; only keep contracts for our target dates
            chain_cache = functions.get_alpaca_option_chain_bulk(t, target_dates=set(all_dates))

            for d in options:
                if d not in all_dates:
                    continue
                option_dt = datetime.strptime(d, "%Y-%m-%d").date()
                today = _date.today()
                earnings_within_dte = earnings_dt is not None and today <= earnings_dt <= option_dt
                ex_div_within_dte = ex_div_dt is not None and today <= ex_div_dt <= option_dt

                is_selling = (d in target_dates and not too_volatile_for_selling
                              and not earnings_within_dte and not ex_div_within_dte)
                is_buying_call = d in config.LONG_TARGET_DATES and not earnings_within_dte and not ex_div_within_dte
                is_buying_put = d in config.LONG_TARGET_DATES and not earnings_within_dte

                need_call = is_selling or is_buying_call
                need_put = is_selling or is_buying_put

                if need_call:
                    call_df = chain_cache.get((d, "call"), pd.DataFrame())
                    if not call_df.empty:
                        if is_selling:
                            try:
                                cc_out.extend(cov_calls.scan_covered_calls(
                                    ticker, stock_exchange, d, min_bid_price, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    sector=sector, industry=industry, beta=beta, hv=hv,
                                    df=call_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass
                        if is_buying_call:
                            try:
                                lc_out.extend(long_calls.scan_long_calls(
                                    ticker, stock_exchange, d, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    hv=hv, sector=sector, industry=industry, beta=beta,
                                    df=call_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass

                if need_put:
                    put_df = chain_cache.get((d, "put"), pd.DataFrame())
                    if not put_df.empty:
                        if is_selling:
                            try:
                                po_out.extend(put_options.scan_put_options(
                                    ticker, stock_exchange, d, min_bid_price, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    sector=sector, industry=industry, beta=beta, hv=hv,
                                    df=put_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass
                        if is_buying_put:
                            try:
                                lp_out.extend(long_puts.scan_long_puts(
                                    ticker, stock_exchange, d, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    hv=hv, sector=sector, industry=industry, beta=beta,
                                    df=put_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass

            return cc_out, lc_out, po_out, lp_out

        def _process_equity_ticker(t: str) -> tuple[list[dict], list[dict]]:
            ticker = Assets.Equity(t, exchanges[stock_exchange])
            ticker_data = ticker.get_info()
            if not ticker_data:
                return [], []

            price = float(ticker_data["price"])
            options = ticker_data["options"]
            fund = ticker_fundamentals.get(t, {})
            sector = fund.get("sector")
            industry = fund.get("industry")
            beta = fund.get("beta")
            ex_dividend_date = fund.get("ex_dividend_date")
            earnings_date = fund.get("earnings_date")
            _today = _date.today()
            if ex_dividend_date:
                try:
                    ex_dividend_date = ex_dividend_date if _date.fromisoformat(ex_dividend_date) >= _today else None
                except ValueError:
                    ex_dividend_date = None
            if earnings_date:
                try:
                    earnings_date = earnings_date if _date.fromisoformat(earnings_date) >= _today else None
                except ValueError:
                    earnings_date = None

            if price > max_stock_price:
                return [], []

            price_data = ticker.get_price_stats()
            if not price_data:
                return [], []

            high_90d = price_data["high_90d"]
            low_90d = price_data["low_90d"]
            ma_20 = price_data["ma_20"]
            ma_50 = price_data["ma_50"]
            avg_price = price_data["avg_price"]
            avg_price_7d = price_data["avg_price_7d"]
            avg_price_30d = price_data["avg_price_30d"]
            trend = price_data["price_trend"]
            rel_std_deviation = price_data["rel_sd"]
            hv = price_data["hv"]

            too_volatile_for_selling = rel_std_deviation > std_dev_threshold

            if len(options) == 0:
                return [], []

            # Combined modes: selling on TARGET_DATES, buying on LONG_TARGET_DATES — single ticker pass
            if option_no in [5, 6]:
                scan_sell = cov_calls.scan_covered_calls if option_no == 5 else put_options.scan_put_options
                scan_buy = long_calls.scan_long_calls if option_no == 5 else long_puts.scan_long_puts
                opt_type = "call" if option_no == 5 else "put"
                selling = []
                buying = []
                earnings_dt = None
                if earnings_date:
                    try:
                        earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                ex_div_dt = None
                if ex_dividend_date:
                    try:
                        ex_div_dt = datetime.strptime(ex_dividend_date, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                for d in options:
                    option_dt = datetime.strptime(d, "%Y-%m-%d").date()
                    today = _date.today()
                    earnings_within_dte = earnings_dt is not None and today <= earnings_dt <= option_dt
                    ex_div_within_dte = ex_div_dt is not None and today <= ex_div_dt <= option_dt
                    is_selling = (d in target_dates and not too_volatile_for_selling
                                  and not earnings_within_dte and not ex_div_within_dte)
                    # Buyers: skip earnings (IV crush risk); long calls also skip ex-div (stock drops hurt calls)
                    is_buying = d in config.LONG_TARGET_DATES and not earnings_within_dte
                    if option_no == 5:  # long calls
                        is_buying = is_buying and not ex_div_within_dte
                    if not is_selling and not is_buying:
                        continue
                    df = functions.get_alpaca_option_chain(t, d, opt_type)
                    if df.empty:
                        continue
                    if is_selling:
                        try:
                            best = scan_sell(
                                ticker, stock_exchange, d, min_bid_price, t, price,
                                high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                avg_price_30d, trend, rel_std_deviation,
                                sector=sector, industry=industry, beta=beta, hv=hv, df=df,
                                ex_dividend_date=ex_dividend_date, earnings_date=earnings_date)
                            selling.extend(best)
                        except Exception:
                            pass
                    if is_buying:
                        try:
                            best = scan_buy(
                                ticker, stock_exchange, d, t, price,
                                high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                avg_price_30d, trend, rel_std_deviation,
                                hv=hv, sector=sector, industry=industry, beta=beta, df=df,
                                ex_dividend_date=ex_dividend_date, earnings_date=earnings_date)
                            buying.extend(best)
                        except Exception:
                            pass
                return selling, buying

            # Single modes (backward compat)
            if too_volatile_for_selling and option_no not in [3, 4]:
                return [], []

            has_long_itm_options = False
            if option_no == 2:
                has_long_itm_options = spread_options.scan_long_cov_calls(options, t, price)

            active_dates = config.LONG_TARGET_DATES if option_no in [3, 4] else target_dates
            matched = []
            for d in options:
                if d not in active_dates:
                    continue
                try:
                    if option_no == 0:
                        best_contracts = cov_calls.scan_covered_calls(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            sector=sector, industry=industry, beta=beta, hv=hv)
                    elif option_no == 1:
                        best_contracts = put_options.scan_put_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            sector=sector, industry=industry, beta=beta, hv=hv)
                    elif option_no == 2 and len(options) > config.SPREAD_MIN_EXPIRY_DATES and has_long_itm_options:
                        best_contracts = spread_options.scan_spread_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            sector=sector, industry=industry, beta=beta, hv=hv)
                    elif option_no == 3:
                        best_contracts = long_calls.scan_long_calls(
                            ticker, stock_exchange, d, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            hv=hv, sector=sector, industry=industry, beta=beta)
                    elif option_no == 4:
                        best_contracts = long_puts.scan_long_puts(
                            ticker, stock_exchange, d, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation,
                            hv=hv, sector=sector, industry=industry, beta=beta)
                    else:
                        best_contracts = []
                except Exception:
                    continue
                matched.extend(best_contracts)

            if option_no in [3, 4]:
                return [], matched
            return matched, []

        if option_no == 7:
            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(_process_equity_ticker_combined, ticker_list))
            for cc, lc, po, lp in results:
                all_cov_calls.extend(cc)
                all_long_calls.extend(lc)
                all_put_options.extend(po)
                all_long_puts.extend(lp)
        else:
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(_process_equity_ticker, ticker_list))
            for selling, buying in results:
                all_selling_contracts.extend(selling)
                all_buying_contracts.extend(buying)

    elif stock_exchange == 2:

        def _process_etf_ticker_combined(t: str) -> tuple[list, list, list, list]:
            """Process one ETF ticker using pre-fetched price/bars data."""
            # Price from bulk prefetch
            trade = prefetched_trades.get(t)
            if not trade:
                return [], [], [], []
            price = float(trade.price)
            if price > max_stock_price:
                return [], [], [], []

            # Price stats from bulk prefetch
            bar_list = prefetched_bars.get(t)
            if not bar_list:
                return [], [], [], []
            price_data = _compute_price_stats_from_bars(t, bar_list)
            if not price_data:
                return [], [], [], []

            # Options expiry list from yfinance (can't be batched)
            try:
                stock = yf.Ticker(t)
                options = _yf_call(lambda: stock.options)
                if not options:
                    return [], [], [], []
            except Exception:
                return [], [], [], []

            # Fundamentals from CSV
            fund = ticker_fundamentals.get(t, {})
            _today = _date.today()
            ex_dividend_date = fund.get("ex_dividend_date") or None
            if ex_dividend_date:
                try:
                    ex_dividend_date = ex_dividend_date if _date.fromisoformat(ex_dividend_date) >= _today else None
                except ValueError:
                    ex_dividend_date = None
            earnings_date = None  # ETFs don't have earnings dates

            ticker = Assets.ETF(t, exchanges[stock_exchange])

            high_90d = price_data["high_90d"]
            low_90d = price_data["low_90d"]
            ma_20 = price_data["ma_20"]
            ma_50 = price_data["ma_50"]
            avg_price = price_data["avg_price"]
            avg_price_7d = price_data["avg_price_7d"]
            avg_price_30d = price_data["avg_price_30d"]
            trend = price_data["price_trend"]
            rel_std_deviation = price_data["rel_sd"]
            hv = price_data.get("hv", 0.0)
            too_volatile_for_selling = rel_std_deviation > std_dev_threshold

            if len(options) == 0:
                return [], [], [], []

            earnings_dt = None
            ex_div_dt = None
            if ex_dividend_date:
                try:
                    ex_div_dt = datetime.strptime(ex_dividend_date, "%Y-%m-%d").date()
                except ValueError:
                    pass

            cc_out, lc_out, po_out, lp_out = [], [], [], []

            # One Alpaca call for the full chain; only keep contracts for our target dates
            chain_cache = functions.get_alpaca_option_chain_bulk(t, target_dates=set(all_dates))

            for d in options:
                if d not in all_dates:
                    continue
                option_dt = datetime.strptime(d, "%Y-%m-%d").date()
                today = _date.today()
                earnings_within_dte = earnings_dt is not None and today <= earnings_dt <= option_dt
                ex_div_within_dte = ex_div_dt is not None and today <= ex_div_dt <= option_dt

                is_selling = (d in target_dates and not too_volatile_for_selling
                              and not earnings_within_dte and not ex_div_within_dte)
                is_buying_call = d in config.LONG_TARGET_DATES and not earnings_within_dte and not ex_div_within_dte
                is_buying_put = d in config.LONG_TARGET_DATES and not earnings_within_dte

                need_call = is_selling or is_buying_call
                need_put = is_selling or is_buying_put

                if need_call:
                    call_df = chain_cache.get((d, "call"), pd.DataFrame())
                    if not call_df.empty:
                        if is_selling:
                            try:
                                cc_out.extend(cov_calls.scan_covered_calls(
                                    ticker, stock_exchange, d, min_bid_price, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    hv=hv, df=call_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass
                        if is_buying_call:
                            try:
                                lc_out.extend(long_calls.scan_long_calls(
                                    ticker, stock_exchange, d, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    hv=hv, df=call_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass

                if need_put:
                    put_df = chain_cache.get((d, "put"), pd.DataFrame())
                    if not put_df.empty:
                        if is_selling:
                            try:
                                po_out.extend(put_options.scan_put_options(
                                    ticker, stock_exchange, d, min_bid_price, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    hv=hv, df=put_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass
                        if is_buying_put:
                            try:
                                lp_out.extend(long_puts.scan_long_puts(
                                    ticker, stock_exchange, d, t, price,
                                    high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                    avg_price_30d, trend, rel_std_deviation,
                                    hv=hv, df=put_df, ex_dividend_date=ex_dividend_date,
                                    earnings_date=earnings_date))
                            except Exception:
                                pass

            return cc_out, lc_out, po_out, lp_out

        def _process_etf_ticker(t: str) -> tuple[list[dict], list[dict]]:
            ticker = Assets.ETF(t, exchanges[stock_exchange])
            ticker_data = ticker.get_info_etf()
            if not ticker_data:
                return [], []

            price = float(ticker_data["price"])
            options = ticker_data["options"]
            fund = ticker_fundamentals.get(t, {})
            ex_dividend_date = fund.get("ex_dividend_date")
            earnings_date = fund.get("earnings_date")
            _today = _date.today()
            if ex_dividend_date:
                try:
                    ex_dividend_date = ex_dividend_date if _date.fromisoformat(ex_dividend_date) >= _today else None
                except ValueError:
                    ex_dividend_date = None
            if earnings_date:
                try:
                    earnings_date = earnings_date if _date.fromisoformat(earnings_date) >= _today else None
                except ValueError:
                    earnings_date = None

            if price > max_stock_price:
                return [], []

            price_data = ticker.get_price_stats()
            if not price_data:
                return [], []

            high_90d = price_data["high_90d"]
            low_90d = price_data["low_90d"]
            ma_20 = price_data["ma_20"]
            ma_50 = price_data["ma_50"]
            avg_price = price_data["avg_price"]
            avg_price_7d = price_data["avg_price_7d"]
            avg_price_30d = price_data["avg_price_30d"]
            trend = price_data["price_trend"]
            rel_std_deviation = price_data["rel_sd"]
            hv = price_data["hv"]

            too_volatile_for_selling = rel_std_deviation > std_dev_threshold

            if len(options) == 0:
                return [], []

            # Combined modes
            if option_no in [5, 6]:
                scan_sell = cov_calls.scan_covered_calls if option_no == 5 else put_options.scan_put_options
                scan_buy = long_calls.scan_long_calls if option_no == 5 else long_puts.scan_long_puts
                opt_type = "call" if option_no == 5 else "put"
                selling = []
                buying = []
                earnings_dt = None
                if earnings_date:
                    try:
                        earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                ex_div_dt = None
                if ex_dividend_date:
                    try:
                        ex_div_dt = datetime.strptime(ex_dividend_date, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                for d in options:
                    option_dt = datetime.strptime(d, "%Y-%m-%d").date()
                    today = _date.today()
                    earnings_within_dte = earnings_dt is not None and today <= earnings_dt <= option_dt
                    ex_div_within_dte = ex_div_dt is not None and today <= ex_div_dt <= option_dt
                    is_selling = (d in target_dates and not too_volatile_for_selling
                                  and not earnings_within_dte and not ex_div_within_dte)
                    is_buying = d in config.LONG_TARGET_DATES and not earnings_within_dte
                    if option_no == 5:  # long calls
                        is_buying = is_buying and not ex_div_within_dte
                    if not is_selling and not is_buying:
                        continue
                    df = functions.get_alpaca_option_chain(t, d, opt_type)
                    if df.empty:
                        continue
                    if is_selling:
                        try:
                            best = scan_sell(
                                ticker, stock_exchange, d, min_bid_price, t, price,
                                high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                avg_price_30d, trend, rel_std_deviation, hv=hv, df=df,
                                ex_dividend_date=ex_dividend_date, earnings_date=earnings_date)
                            selling.extend(best)
                        except Exception:
                            pass
                    if is_buying:
                        try:
                            best = scan_buy(
                                ticker, stock_exchange, d, t, price,
                                high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                                avg_price_30d, trend, rel_std_deviation, hv=hv, df=df,
                                ex_dividend_date=ex_dividend_date, earnings_date=earnings_date)
                            buying.extend(best)
                        except Exception:
                            pass
                return selling, buying

            # Single modes (backward compat)
            if too_volatile_for_selling and option_no not in [3, 4]:
                return [], []

            active_dates = config.LONG_TARGET_DATES if option_no in [3, 4] else target_dates
            matched = []
            for d in options:
                if d not in active_dates:
                    continue
                try:
                    if option_no == 0:
                        best_contracts = cov_calls.scan_covered_calls(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation, hv=hv)
                    elif option_no == 1:
                        best_contracts = put_options.scan_put_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation, hv=hv)
                    elif option_no == 2 and len(options) > config.SPREAD_MIN_EXPIRY_DATES:
                        best_contracts = spread_options.scan_spread_options(
                            ticker, stock_exchange, d, min_bid_price, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation, hv=hv)
                    elif option_no == 3:
                        best_contracts = long_calls.scan_long_calls(
                            ticker, stock_exchange, d, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation, hv=hv)
                    elif option_no == 4:
                        best_contracts = long_puts.scan_long_puts(
                            ticker, stock_exchange, d, t, price,
                            high_90d, low_90d, avg_price, ma_20, ma_50, avg_price_7d,
                            avg_price_30d, trend, rel_std_deviation, hv=hv)
                    else:
                        best_contracts = []
                except Exception:
                    continue
                matched.extend(best_contracts)

            if option_no in [3, 4]:
                return [], matched
            return matched, []

        if option_no == 7:
            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(_process_etf_ticker_combined, ticker_list))
            for cc, lc, po, lp in results:
                all_cov_calls.extend(cc)
                all_long_calls.extend(lc)
                all_put_options.extend(po)
                all_long_puts.extend(lp)
        else:
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(_process_etf_ticker, ticker_list))
            for selling, buying in results:
                all_selling_contracts.extend(selling)
                all_buying_contracts.extend(buying)

    if option_no == 7:
        cc_sorted = sorted(all_cov_calls, key=lambda x: x["option_yield"], reverse=True)
        lc_sorted = sorted(all_long_calls, key=lambda x: x["iv_hv_ratio"] if x["iv_hv_ratio"] is not None else 999)
        po_sorted = sorted(all_put_options, key=lambda x: x["option_yield"], reverse=True)
        lp_sorted = sorted(all_long_puts, key=lambda x: x["iv_hv_ratio"] if x["iv_hv_ratio"] is not None else 999)

        print(f"Covered calls: {len(cc_sorted)}, Long calls: {len(lc_sorted)}, "
              f"Put options: {len(po_sorted)}, Long puts: {len(lp_sorted)}")
        print()

        sfx = {0: "nyse", 1: "nasdaq", 2: "arca"}[stock_exchange]
        ex_no = stock_exchange
        functions.write_best_options_to_json(OUTPUT_DIR / f"best_cov_calls_{sfx}.json", ex_no, cc_sorted)
        functions.write_best_options_to_json(OUTPUT_DIR / f"best_long_calls_{sfx}.json", ex_no, lc_sorted, buying_side=True)
        functions.write_best_options_to_json(OUTPUT_DIR / f"best_put_options_{sfx}.json", ex_no, po_sorted)
        functions.write_best_options_to_json(OUTPUT_DIR / f"best_long_puts_{sfx}.json", ex_no, lp_sorted, buying_side=True)

    else:
        selling_sorted = sorted(all_selling_contracts, key=lambda x: x["option_yield"], reverse=True)
        buying_sorted = sorted(
            all_buying_contracts,
            key=lambda x: x["iv_hv_ratio"] if x["iv_hv_ratio"] is not None else 999)

        print(f"Selling contracts: {len(selling_sorted)}, Buying contracts: {len(buying_sorted)}")
        print()

        # Combined call scan: covered calls (selling) + long calls (buying)
        if option_no == 5:
            if stock_exchange == 0:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_cov_calls_nyse.json", 0, selling_sorted)
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_calls_nyse.json", 0, buying_sorted, buying_side=True)
            elif stock_exchange == 1:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_cov_calls_nasdaq.json", 1, selling_sorted)
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_calls_nasdaq.json", 1, buying_sorted, buying_side=True)
            elif stock_exchange == 2:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_cov_calls_arca.json", 2, selling_sorted)
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_calls_arca.json", 2, buying_sorted, buying_side=True)

        # Combined put scan: put options (selling) + long puts (buying)
        elif option_no == 6:
            if stock_exchange == 0:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_put_options_nyse.json", 0, selling_sorted)
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_puts_nyse.json", 0, buying_sorted, buying_side=True)
            elif stock_exchange == 1:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_put_options_nasdaq.json", 1, selling_sorted)
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_puts_nasdaq.json", 1, buying_sorted, buying_side=True)
            elif stock_exchange == 2:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_put_options_arca.json", 2, selling_sorted)
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_puts_arca.json", 2, buying_sorted, buying_side=True)

        # Single modes (backward compat)
        elif option_no == 0:
            if stock_exchange == 0:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_cov_calls_nyse.json", 0, selling_sorted)
            elif stock_exchange == 1:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_cov_calls_nasdaq.json", 1, selling_sorted)
            elif stock_exchange == 2:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_cov_calls_arca.json", 2, selling_sorted)
        elif option_no == 1:
            if stock_exchange == 0:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_put_options_nyse.json", 0, selling_sorted)
            elif stock_exchange == 1:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_put_options_nasdaq.json", 1, selling_sorted)
            elif stock_exchange == 2:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_put_options_arca.json", 2, selling_sorted)
        elif option_no == 3:
            if stock_exchange == 0:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_calls_nyse.json", 0, buying_sorted, buying_side=True)
            elif stock_exchange == 1:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_calls_nasdaq.json", 1, buying_sorted, buying_side=True)
            elif stock_exchange == 2:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_calls_arca.json", 2, buying_sorted, buying_side=True)
        elif option_no == 4:
            if stock_exchange == 0:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_puts_nyse.json", 0, buying_sorted, buying_side=True)
            elif stock_exchange == 1:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_puts_nasdaq.json", 1, buying_sorted, buying_side=True)
            elif stock_exchange == 2:
                functions.write_best_options_to_json(OUTPUT_DIR / "best_long_puts_arca.json", 2, buying_sorted, buying_side=True)

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
