# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the screener

```bash
# Run all 9 scans unattended (calls/puts/spreads × NYSE/NASDAQ/ARCA)
python main.py
```

The scan order is defined by `SCANS` in `main.py`:
calls NYSE → puts NASDAQ → spreads ARCA → calls NASDAQ → puts ARCA → spreads NYSE → calls ARCA → puts NYSE → spreads NASDAQ

There are no tests or a lint step in this project.

## Environment setup

**conda (local development):**
```bash
conda env create -f environment.yml
conda activate option_screener_oop
pip install py_vollib python-dateutil
```

**pip/venv (production server, CI):**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Pinned packages: `alpaca-py==0.43.5`, `yfinance==0.2.59`, `curl-cffi==0.10.0`, `py_vollib==1.0.1`. Python 3.10 required.

**`.env` file** — create in the project root (never committed):

```
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
OUTPUT_DIR=/path/to/options-saas-refactored-phase1/shared/data
```

`ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are loaded at import time by `alpaca_client.py` via `python-dotenv`. `OUTPUT_DIR` is read by `main.py` at startup. The screener will raise `RuntimeError` on startup if any of the three are missing.

## Architecture

The screener iterates over a ticker list, fetches market data via Alpaca (price, historical bars, options chain) and yfinance (expiry dates list, sector/industry/beta), applies filters, and writes matching option contracts to JSON files consumed by a separate `options-saas` frontend.

**Ticker files** live in `tickers/` (gitignored — runtime data, updated each full scan):
- `nyse_options.txt`, `nasdaq_options.txt`, `arca_options.txt` — filtered lists (tickers with options, `SCOPE=0`)
- `nyse_full.txt`, `nasdaq_full.txt`, `arca_full.txt` — full exchange lists (`SCOPE=1`)

`main.py` resolves paths via `TICKERS_DIR = Path(__file__).parent / "tickers"`.

**Data flow:**
1. `main.py` reads a ticker list from `tickers/` (file chosen by `SCOPE` in `config.py` and the exchange passed to `main()`)
2. For each ticker it instantiates either `Assets.Equity` or `Assets.ETF`
3. It calls `.get_info()` / `.get_info_etf()` and `.get_price_stats()` — both return dicts or `{}` on failure
4. Pre-filters: price > exchange threshold and `rel_std_deviation > STD_DEV_THRESHOLD` skip the ticker
5. The matching option module's `scan_*` function is called for each expiry date in `config.TARGET_DATES` (auto-computed next 3 Fridays)
6. Matched contracts (dicts) are collected, sorted by `option_yield` descending, and written to JSON via `functions.write_best_options_to_json()`

**Module responsibilities:**
- `config.py` — all tunable globals and filter thresholds. `TARGET_DATES` is auto-computed (next 3 Fridays). `TYPE` is no longer edited per run — the full automated run cycles all 9 combinations. Exchange-specific thresholds (`NYSE_NASDAQ_MAX_STOCK_PRICE`, `ARCA_MAX_STOCK_PRICE`, `NYSE_NASDAQ_MIN_BID_PRICE`, `ARCA_MIN_BID_PRICE`, `STRIKE_PRICE_THRESHOLD`) are read inside `main()` from the actual exchange argument. Spread-specific filters (`SPREAD_MIN_EXPIRY_DATES`, `SPREAD_MIN_ITM_DISTANCE`) are also defined here.
- `alpaca_client.py` — initializes `StockHistoricalDataClient` and `OptionHistoricalDataClient` from `.env` credentials; exposes a token-bucket `_RateLimiter` (180/min) and three rate-limited wrappers (`get_latest_trades`, `get_stock_bars`, `get_option_chain`) used by `Assets.py` and `functions.py`
- `Assets.py` — `Asset` base class; `Equity` and `ETF` subclasses. Price via Alpaca `StockLatestTradeRequest`; historical bars via Alpaca `StockBarsRequest`; options expiry list and fundamentals (sector/industry/beta) still via yfinance
- `functions.py` — shared utilities: `get_alpaca_option_chain` (Alpaca options snapshots → DataFrame), `compute_main_trend`, `sigma_distance_to_strike`, `estimate_delta` (uses `py_vollib` Black-Scholes), `get_std_dev`, `get_price_trend` (linear regression), `write_best_options_to_json`
- `covered_calls.py` — single `scan_covered_calls` handling both Equity and ETF; equity fields (`sector`, `industry`, `beta`) added when `exchange in [0, 1]`
- `put_options.py` — single `scan_put_options` handling both Equity and ETF; same equity field pattern
- `spread_options.py` — `scan_long_cov_calls` (pre-check for deep ITM long calls) + `scan_spread_options` (alias of `scan_covered_calls` from covered_calls)

## Key metrics

- **CoV (coeff_variation)** — relative std dev `(std_dev / avg_price) * 100`; above `STD_DEV_THRESHOLD` (default 15) skips the ticker
- **Moneyness** — calls/spreads: `((strike - price) / price) * 100`; puts: `((price - strike) / price) * 100`
- **Sigma distance** — implied std devs from current price to strike: `|ln(S/K)| / (IV * sqrt(T/365))`
- **option_yield** — calls/spreads: `(bid / price) * 100`; puts: `(bid / strike) * 100`; pivot field for sorting output
- **roc** — annualized option_yield: `option_yield * (365 / DTE)`
- **break_even** — calls/spreads: `price - bid`; puts: `strike - bid`

## Output

JSON files are written to the path set by `OUTPUT_DIR` in `.env` (e.g. `shared/data/` in the main repo), with names like `best_cov_calls_nyse.json`, `best_put_options_nasdaq.json`, `best_spreads_arca.json`. Equity contracts have 30 fields; ETF contracts have 27 (no `sector`, `industry`, `beta`).

## Rollback points

Tag **`pre-alpaca-migration`** (commit `6335d9c`) marks the last stable state before the Alpaca migration.

Tag **`pre-threading-refactor`** (commit `ae7560f`) marks the last stable state before the threading + rate-limiter refactor.

Tag **`pre-merge-cleanup`** (commit `2aa7941`) marks the last stable state before merging into `options-saas-refactored-phase1` as the `scanner/` module. Ticker files live in `tickers/`, output path is driven by `OUTPUT_DIR` env var, `requirements.txt` is present.

To roll back to any tag:

```bash
git checkout main
git reset --hard <tag-name>
git push --force origin main   # only if broken changes were already pushed
```

## Threading and rate limiting

The screener uses `concurrent.futures.ThreadPoolExecutor` to process tickers in parallel (I/O-bound workload — threads, not processes).

**Rate limiter** — `alpaca_client.py` exposes a module-level `_RateLimiter` (token bucket, 180 calls/min — conservative buffer under Alpaca's 200/min ceiling) and three thin wrapper functions that every Alpaca call goes through:
- `alpaca_client.get_latest_trades(req)` — used by `Assets.get_info()` / `get_info_etf()`
- `alpaca_client.get_stock_bars(req)` — used by `Assets.get_price_stats()`
- `alpaca_client.get_option_chain(req)` — used by `functions.get_alpaca_option_chain()`

**Parallelism** — `main.py` extracts per-ticker logic into `_process_equity_ticker()` and `_process_etf_ticker()`, then maps them over `ticker_list` with `ThreadPoolExecutor(max_workers=8)`. The rate limiter is the throughput ceiling; adding more workers beyond ~8 yields no benefit.

**Prints** — per-ticker status prints (`Scanning stock…`, `Match!`) and the market index/VIX header block were removed. Each scan prints a scan header (e.g. `Scan 3/9: Spread — ARCA`) and footer (contract count, execution time). The full run prints a total elapsed time at the end.

## Data sources

**Alpaca** (primary — requires free brokerage account at alpaca.markets):
- Current price → `StockLatestTradeRequest` in `Assets.get_info()` / `get_info_etf()`
- 90-day historical bars → `StockBarsRequest` in `Assets.get_price_stats()`
- Options chain (bid/ask/IV per expiry) → `OptionChainRequest` in `functions.get_alpaca_option_chain()`
- Production limit: **200 requests/minute** (rate limiter set to 180 as a safety buffer)

**yfinance** (retained for stable/non-real-time data only):
- Options expiry date list → `yf.Ticker(symbol).options` in `Assets.get_info()` / `get_info_etf()`
- Sector, industry, beta → `yf.Ticker(symbol).info` in `Assets.Equity.get_info()` (equities only)

yfinance is pinned at `0.2.59` to avoid breakage from undocumented API changes.

## config.py — what to change per run

| Variable | Values | Effect |
|---|---|---|
| `TYPE` | 0=call, 1=put, 2=spread | No longer edited — full run cycles all types |
| `TARGET_DATES` | auto-computed | Next 3 Fridays from today; no manual edit needed |
| `SCOPE` | 0=tickers with options only, 1=full list | Input ticker file |
| `RISK_FREE_RATE` | float (%) | 1-month Treasury rate used for delta calculation |
| `STD_DEV_THRESHOLD` | default 15 | Tickers with CoV above this are skipped |
| `OPTION_YIELD_THRESHOLD` | default 25 | Contracts with yield above this are skipped (unrealistic) |
| `NYSE_NASDAQ_MAX_STOCK_PRICE` | default 50 | Price ceiling for NYSE/NASDAQ tickers |
| `ARCA_MAX_STOCK_PRICE` | default 200 | Price ceiling for ARCA tickers |
| `NYSE_NASDAQ_MIN_BID_PRICE` | default 0.2 | Minimum bid for NYSE/NASDAQ contracts |
| `ARCA_MIN_BID_PRICE` | default 0.5 | Minimum bid for ARCA contracts |
| `SPREAD_MIN_EXPIRY_DATES` | default 10 | Min number of expiry dates a ticker must have for spread scans |
| `SPREAD_MIN_ITM_DISTANCE` | default 6 | Min $ distance between strike and price for ITM long call in spread |

## Known issues

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | `spread_options_short_calls.py` — wrong API, crashes | Critical | Done |
| 2 | `int(None)` crash on null `openInterest` silently drops contracts | Critical | Done |
| 3 | `sigma_distance` is 100× too small | Critical | Done |
| 4 | Put `break_even` uses call formula | Critical | Done |
| 5 | 6× duplicated scan logic | Non-critical | Done |
| 6 | All exceptions silently swallowed | Non-critical | Won't fix |
| 7 | `days_to_expiration()` called per row instead of per expiry | Non-critical | Done (with #5) |
| 8 | Dead NaN checks on `option_yield` | Non-critical | Done (with #5) |
| 9 | `config.TREND` never applied as a filter | Non-critical | Done |
| 10 | Network calls at module level in `main.py` | Non-critical | Done |
| 11 | Dead `write_best_option_to_file*` functions | Non-critical | Done |
| 12 | `main.py:105` — `float(beta)` crashes when yfinance returns `beta=None` | Critical | Done |
| 13 | `main.py:54` — `dow_jones_1m` used as truthy instead of `< 0`; wrong warning condition | Bug | Done |
| 14 | `spread_options.py:43` — `return False` inside the for loop; stops after first qualifying date; returns `None` implicitly when no dates qualify | Bug | Done |
| 15 | `spread_options.py:31` — returns `[]` instead of `False` (wrong type, works by accident) | Bug | Done |
| 16 | `Assets.py:173` — `float()` called before None check; null guard is dead code | Bug | Done |
| 17 | `covered_calls.py:45-48` — NaN bid check comes after comparison that passes NaN through (fragile ordering) | Non-critical | Done |
| 18 | `main.py:32` — default `exchange_number=2` hardcodes ARCA; ignores `config.STOCK_EXCHANGE` | Non-critical | Done |
| 19 | `main.py:63-73` — ticker list file handle never closed (no `with` block) | Non-critical | Done |
| 20 | `spread_options.py:19` — dead `new_date` variable and dead `datetime` import | Non-critical | Done |
| 21 | `config.py` — `SPREAD_STRIKE_PRICE_THRESHOLD` defined but never referenced | Non-critical | Done |
| 22 | `Assets.py` — `exchange` property and `get_price_stats` logic duplicated across `Equity` and `ETF` | Architecture | Done |
| 23 | `functions.py:241` — extra `yf.Ticker().info` call for last price already available in downloaded data | Non-critical | Done |
| 24 | `spread_options_short_calls.py:54` — `get_price_stats_etf()` called but removed by #22 refactor; crashes at runtime | Critical | Done (file deleted) |
| 25 | `functions.py:159` — `normalize_nullable_fields()` returns `str`, so `beta` in contracts is a string not a float | Bug | Done |
| 26 | `main.py:455` — interactive prompts have no input validation; invalid input crashes or passes wrong value | Bug | Done |
| 27 | `spread_options_short_calls.py:92` — hardcoded `1.5` threshold instead of `config.STRIKE_PRICE_THRESHOLD` (3 for ARCA) | Bug | Done (file deleted) |
| 28 | `functions.py:13` — duplicate `from datetime import date, datetime` | Non-critical | Done |
| 29 | `functions.py:252` — `get_last_index_price()` is dead code after #23 fix | Non-critical | Done |
| 30 | `main.py:18` — `option_no = config.TYPE` at module level shadowed by local in `main()`; dead | Non-critical | Done |
| 31 | `main.py:29` — `have_options = config.HAVE_OPTIONS` imported but never used | Non-critical | Done |
| 32 | `main.py:7` — `import csv` unused | Non-critical | Done |
| 33 | `config.py` — `TEST` and `HAVE_OPTIONS` defined but never referenced | Non-critical | Done |
| 34 | `Assets.py` — unused imports: `datetime`, `requests_cache`, `requests`, `numpy`, `pandas` | Non-critical | Done |
| 35 | `functions.py:7` — `import csv` unused | Non-critical | Done |
| 36 | `alpaca_client.py` — `get_latest_stock_trades` doesn't exist; correct method is `get_stock_latest_trade` — every `get_info()` call raised `AttributeError`, silently returning `{}` and skipping all tickers | Critical | Done |
| 37 | `functions.py` — `snap.implied_volatility or 0.0` stored IV=0 for contracts where Alpaca returns `None`; first such row passing the bid filter caused `ZeroDivisionError` in `py_vollib` (sigma=0), propagating through the scan function to `main.py`'s bare `except`, silently dropping all contracts for that date | Critical | Done |
| 38 | `functions.py` — `snap.open_interest` doesn't exist on `OptionsSnapshot` in alpaca-py 0.43.5; `AttributeError` propagated through every option chain call | Critical | Done |
| 39 | `main.py` — `MAX_STOCK_PRICE`, `MIN_BID_PRICE`, `STRIKE_PRICE_THRESHOLD` computed at module load from `config.STOCK_EXCHANGE`; in a multi-exchange run they stayed fixed to the load-time exchange, giving ARCA scans NYSE thresholds | Bug | Done |
| 40 | `covered_calls.py`, `put_options.py` — `365 / dte` raises `ZeroDivisionError` if scanner runs on exact expiry date (dte=0); `sigma_distance_to_strike` also raises `ValueError` | Bug | Done |
| 41 | `config.py` — `STOCK_EXCHANGE`, `WRITE_TICKERS_TO_FILE`, `TREND_DOWN/SIDEWAYS/UP`, `MAX_STOCK_PRICE`, `MIN_BID_PRICE` defined but never referenced outside config | Non-critical | Done |
| 42 | `main.py`, `spread_options.py` — filter thresholds scattered as magic numbers (`50`, `200`, `0.2`, `0.5`, `10`, `6`) instead of named constants | Non-critical | Done |
| 43 | `functions.py` — `get_vix()` and `get_index_change_last5d()` dead code (never called); `import sys` only referenced by these two functions | Non-critical | Done |
