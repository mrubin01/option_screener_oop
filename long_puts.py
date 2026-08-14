import Assets
from typing import Any
import config
import math
import functions


def scan_long_puts(
    ticker: Assets.Equity | Assets.ETF,
    exchange: int,
    option_date: str,
    symbol: str,
    current_price: float,
    lowest_price: float,
    highest_price: float,
    avg_price: float,
    avg_price_7d: float,
    avg_price_30d: float,
    trend: int,
    rel_std_deviation: float,
    hv: float = 0.0,
    sector: str | None = None,
    industry: str | None = None,
    beta: float | None = None,
    df=None,
    ex_dividend_date: str | None = None,
    earnings_date: str | None = None,
) -> list[dict[str, Any]]:

    matched_contracts = []

    puts = df if df is not None else functions.get_alpaca_option_chain(symbol, option_date, "put")
    if puts is None or puts.empty:
        return []

    main_trend = functions.compute_main_trend(current_price, avg_price, avg_price_7d, avg_price_30d, trend)
    if main_trend > 0:
        return []

    dte = functions.days_to_expiration(option_date)
    if dte <= 0:
        return []

    for row in puts.itertuples(index=False):
        ask = row.ask if not (isinstance(row.ask, float) and math.isnan(row.ask)) else 0.0

        if ask < config.LONG_MIN_ASK or ask > config.LONG_MAX_ASK:
            continue

        if row.strike >= current_price:
            continue

        moneyness = round(((current_price - float(row.strike)) / current_price) * 100, 2)
        if moneyness > config.LONG_MAX_MONEYNESS:
            continue

        if row.openInterest < config.LONG_MIN_OPEN_INTEREST:
            continue

        iv_hv_ratio = round(row.impliedVolatility / hv, 2) if hv > 0 else None
        if iv_hv_ratio is not None and iv_hv_ratio > config.LONG_MAX_IV_HV_RATIO:
            continue

        spread_bid_ask = round(row.ask - row.bid, 2)
        spread_strike_price = round(abs(row.strike - current_price), 2)
        break_even = round(float(row.strike) - ask, 2)
        max_profit_per_share = round(float(row.strike) - ask, 2)

        est_delta = functions.estimate_delta("put", current_price, row.strike, dte, config.RISK_FREE_RATE, row.impliedVolatility)
        if float(est_delta) < config.LONG_MIN_DELTA:
            continue

        tot_return = round(((float(row.strike) - ask) / current_price) * 100, 2)
        sigma_distance = functions.sigma_distance_to_strike(
            current_price, float(row.strike), float(row.impliedVolatility), dte
        )

        profit_5pct = round(float(row.strike) * 0.05 - ask, 2)
        return_5pct = round((profit_5pct / ask) * 100, 2) if ask > 0 else 0.0
        profit_10pct = round(float(row.strike) * 0.10 - ask, 2)
        return_10pct = round((profit_10pct / ask) * 100, 2) if ask > 0 else 0.0

        contract = {
            "ticker": ticker.symbol,
            "exchange": exchange,
            "contract": row.contractSymbol,
            "expiry_date": option_date,
            "days_to_expiration": dte,
            "current_price": round(current_price, 2),
            "coeff_variation": rel_std_deviation,
            "max_profit": max_profit_per_share,
            "max_profit_per_contract": round(max_profit_per_share * 100, 2),
            "otm": round(float(spread_strike_price), 2),
            "strike_price": round(float(row.strike), 2),
            "moneyness": moneyness,
            "sigma_distance": round(sigma_distance, 2),
            "ask_per_share": round(float(ask), 2),
            "premium_per_contract": round(float(ask * 100), 2),
            "spread_bid_ask": round(float(spread_bid_ask), 2),
            "break_even": break_even,
            "open_interest": int(row.openInterest) if row.openInterest is not None and not (isinstance(row.openInterest, float) and math.isnan(row.openInterest)) else 0,
            "impl_volatility": round(float(row.impliedVolatility * 100), 2),
            "tot_return": tot_return,
            "profit_5pct": profit_5pct,
            "return_5pct": return_5pct,
            "profit_10pct": profit_10pct,
            "return_10pct": return_10pct,
            "delta": est_delta,
            "highest_price": highest_price,
            "avg_price": avg_price,
            "lowest_price": lowest_price,
            "main_trend": main_trend,
            "iv_hv_ratio": iv_hv_ratio,
            "ex_dividend_date": ex_dividend_date,
            "earnings_date": earnings_date,
        }

        if exchange in [0, 1]:
            contract["sector"] = sector
            contract["industry"] = industry
            contract["beta"] = beta

        matched_contracts.append(contract)

    return matched_contracts


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
