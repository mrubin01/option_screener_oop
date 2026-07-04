import Assets
from typing import Any
import config
import math
import functions


def scan_put_options(
    ticker: Assets.Equity | Assets.ETF,
    exchange: int,
    option_date: str,
    threshold_bid: float,
    symbol: str,
    current_price: float,
    lowest_price: float,
    highest_price: float,
    avg_price: float,
    avg_price_7d: float,
    avg_price_30d: float,
    trend: int,
    rel_std_deviation: float,
    sector: str | None = None,
    industry: str | None = None,
    beta: float | None = None,
) -> list[dict[str, Any]]:

    matched_contracts = []

    if threshold_bid < 0:
        raise ValueError("threshold_bid must be non-negative")

    puts = functions.get_alpaca_option_chain(symbol, option_date, "put")
    if puts is None or puts.empty:
        return []

    main_trend = functions.compute_main_trend(current_price, avg_price, avg_price_7d, avg_price_30d, trend)
    dte = functions.days_to_expiration(option_date)

    for row in puts.itertuples(index=False):
        if isinstance(row.bid, float) and math.isnan(row.bid):
            continue

        if row.bid < threshold_bid or row.strike >= current_price:
            continue

        spread_bid_ask = round(row.ask - row.bid, 2)
        spread_strike_price = round(abs(row.strike - current_price), 2)
        delta_price_premium = row.bid
        break_even = round(row.strike - row.bid, 2)

        if isinstance(spread_bid_ask, float) and math.isnan(spread_bid_ask):
            continue

        if (isinstance(spread_strike_price, float) and math.isnan(spread_strike_price)) or \
                spread_strike_price <= config.STRIKE_PRICE_THRESHOLD:
            continue

        if isinstance(delta_price_premium, float) and math.isnan(delta_price_premium):
            continue

        est_delta = functions.estimate_delta("put", current_price, row.strike, dte, config.RISK_FREE_RATE, row.impliedVolatility)

        option_yield = round((row.bid / row.strike) * 100, 2)
        if option_yield >= config.OPTION_YIELD_THRESHOLD:
            continue

        annualized_option_yield = round(option_yield * (365 / dte), 2)
        tot_return = round((row.bid / current_price) * 100, 2)
        moneyness = round(((current_price - float(row.strike)) / current_price) * 100, 2)
        sigma_distance = functions.sigma_distance_to_strike(
            current_price, float(row.strike), float(row.impliedVolatility), dte
        )

        contract = {
            "ticker": ticker.symbol,
            "exchange": exchange,
            "contract": row.contractSymbol,
            "expiry_date": option_date,
            "days_to_expiration": dte,
            "current_price": round(current_price, 2),
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

        if exchange in [0, 1]:
            contract["sector"] = sector
            contract["industry"] = industry
            contract["beta"] = beta

        matched_contracts.append(contract)

    return matched_contracts


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
