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
- `functions.py` — shared utilities: `compute_main_trend`, `sigma_distance_to_strike`, `estimate_delta` (uses `py_vollib` Black-Scholes), `get_std_dev`, `get_price_trend` (linear regression), `write_best_options_to_json`
- `covered_calls.py` — single `scan_covered_calls` handling both Equity and ETF; equity fields (`sector`, `industry`, `beta`) added when `exchange in [0, 1]`
- `put_options.py` — single `scan_put_options` handling both Equity and ETF; same equity field pattern
- `spread_options.py` — `scan_long_cov_calls` (pre-check for deep ITM long calls) + `scan_spread_options` (alias of `scan_covered_calls` from covered_calls)
- `spread_options_short_calls.py` — standalone `run()` for the short-call leg of spreads (ARCA/ETF only)

## Key metrics

- **CoV (coeff_variation)** — relative std dev `(std_dev / avg_price) * 100`; above `STD_DEV_THRESHOLD` (default 15) skips the ticker
- **Moneyness** — calls/spreads: `((strike - price) / price) * 100`; puts: `((price - strike) / price) * 100`
- **Sigma distance** — implied std devs from current price to strike: `|ln(S/K)| / (IV * sqrt(T/365))`
- **option_yield** — calls/spreads: `(bid / price) * 100`; puts: `(bid / strike) * 100`; pivot field for sorting output
- **roc** — annualized option_yield: `option_yield * (365 / DTE)`
- **break_even** — calls/spreads: `price - bid`; puts: `strike - bid`

## Output

JSON files are written to `~/options-saas/shared/data/` with names like `best_cov_calls_nyse.json`, `best_put_options_nasdaq.json`, `best_spreads_arca.json`. Equity contracts have 30 fields; ETF contracts have 27 (no `sector`, `industry`, `beta`).

## Planned migration: yfinance → Tradier

yfinance is an unofficial reverse-engineered wrapper around Yahoo Finance's undocumented API. Key risks: breaking changes without notice, silent throttling, unpredictable None/NaN fields. The version is pinned at `0.2.59` to avoid breakage.

**Tradier brokerage API** is the planned replacement:
- Requires a free Tradier brokerage account (no minimum balance)
- Production tier: **120 requests/minute** (vs ~60 unofficial limit with yfinance)
- Real-time bid/ask, options chains, open interest from an actual broker feed
- Stable documented JSON schema — eliminates the None/NaN field surprises
- Python: use the `tradier` client library or plain `requests`
- Docs: developer.tradier.com

**Scope of migration when ready:**
- `Assets.py` — replace `get_info()`, `get_info_etf()` with Tradier quotes endpoint
- `Assets.py` — replace `get_price_stats()` with Tradier historical data endpoint
- `covered_calls.py`, `put_options.py` — replace `stock.option_chain(date).calls/puts` with Tradier options chain endpoint
- `functions.py` — `get_index_change_last5d()` and `get_vix()` may stay on yfinance (index data) or switch to a free alternative
- `main.py` — minimal changes; consumes dicts from the above methods

## config.py — what to change per run

| Variable | Values | Effect |
|---|---|---|
| `TYPE` | 0=call, 1=put, 2=spread | Which option module runs |
| `STOCK_EXCHANGE` | 0=NYSE, 1=NASDAQ, 2=ARCA | Ticker list and asset class used |
| `YEAR/MONTH/DAY` | lists | Target expiry dates to scan |
| `SCOPE` | 0=tickers with options only, 1=full list | Input ticker file |

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
