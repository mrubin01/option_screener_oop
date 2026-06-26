# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the screener

```bash
# Run with default exchange (ARCA, exchange=2)
python main.py

# Run with a specific exchange (0=NYSE, 1=NASDAQ, 2=ARCA)
python main.py 0
python main.py 1
```

There are no tests or a lint step in this project.

## Environment setup

```bash
conda env create -f environment.yml
conda activate option_screener_oop
pip install py_vollib python-dateutil
```

Key pinned versions: `yfinance==0.2.59`, `curl-cffi==0.10.0`, Python 3.10.

## Architecture

The screener iterates over a ticker list, fetches market data via yfinance, applies filters, and writes matching option contracts to JSON files consumed by a separate `options-saas` frontend.

**Data flow:**
1. `main.py` reads a ticker list from a hardcoded `.txt` file (path depends on `STOCK_EXCHANGE` and `SCOPE` in `config.py`)
2. For each ticker it instantiates either `Assets.Equity` or `Assets.ETF`
3. It calls `.get_info()` / `.get_info_etf()` and `.get_price_stats()` / `.get_price_stats_etf()` — both return dicts or `{}` on failure
4. Pre-filters: price > `MAX_STOCK_PRICE` and `rel_std_deviation > STD_DEV_THRESHOLD` skip the ticker
5. The matching option module's `scan_*` function is called for each expiry date matching `(YEAR, MONTH, DAY)` in config
6. Matched contracts (dicts) are collected, sorted by `option_yield` descending, and written to JSON via `functions.write_best_options_to_json()`

**Module responsibilities:**
- `config.py` — all tunable globals (`TYPE`, `STOCK_EXCHANGE`, `YEAR/MONTH/DAY`, thresholds). Edit this before each run.
- `Assets.py` — `Asset` base class; `Equity` and `ETF` subclasses wrapping yfinance calls
- `functions.py` — shared utilities: `sigma_distance_to_strike`, `estimate_delta` (uses `py_vollib` Black-Scholes), `get_std_dev`, `get_price_trend` (linear regression), `write_best_options_to_json`
- `covered_calls.py` — `scan_covered_calls` / `scan_etf_covered_calls`
- `put_options.py` — `scan_put_options` / `scan_etf_put_options`
- `spread_options.py` — `scan_long_cov_calls` (pre-check for deep ITM long calls) + `scan_spread_options` / `scan_etf_spread_options`
- `spread_options_short_calls.py` — standalone script for short-call side of spreads (ARCA only)

## Key metrics

- **CoV (coeff_variation)** — relative std dev `(std_dev / avg_price) * 100`; above `STD_DEV_THRESHOLD` (default 15) skips the ticker
- **Moneyness** — `((strike - current_price) / current_price) * 100`; for puts it measures how far OTM downward
- **Sigma distance** — implied std devs from current price to strike: `|ln(S/K)| / (IV * sqrt(T/365)) / 100`
- **option_yield** — `(bid / current_price) * 100`; pivot field for sorting output
- **roc** — annualized option_yield: `option_yield * (365 / DTE)`

## Output

JSON files are written to `~/options-saas/shared/data/` with names like `best_cov_calls_nyse.json`, `best_put_options_nasdaq.json`, `best_spreads_arca.json`. Equity contracts have 30 fields; ETF contracts have 27 (no `sector`, `industry`, `beta`).

## config.py — what to change per run

| Variable | Values | Effect |
|---|---|---|
| `TYPE` | 0=call, 1=put, 2=spread | Which option module runs |
| `STOCK_EXCHANGE` | 0=NYSE, 1=NASDAQ, 2=ARCA | Ticker list and asset class used |
| `YEAR/MONTH/DAY` | lists | Target expiry dates to scan |
| `SCOPE` | 0=tickers with options only, 1=full list | Input ticker file |
| `TREND` | -1=any, 0=downtrend, 1=uptrend | Filter by price trend (not enforced in all paths) |
