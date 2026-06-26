import yfinance
import Assets
from typing import Any
import config
import math
import functions


def scan_covered_calls(
    ticker: Assets.Equity | Assets.ETF,
    exchange: int,
    option_date: str,
    threshold_bid: float,
    stock: yfinance.Ticker,
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

    try:
        cc = stock.option_chain(option_date).calls
    except Exception:
        return []

    if cc is None or cc.empty:
        return []

    main_trend = functions.compute_main_trend(current_price, avg_price, avg_price_7d, avg_price_30d, trend)
    dte = functions.days_to_expiration(option_date)

    for row in cc.itertuples(index=False):
        if row.bid < threshold_bid or row.strike <= current_price:
            continue

        if isinstance(row.bid, float) and math.isnan(row.bid):
            continue

        spread_bid_ask = round(row.ask - row.bid, 2)
        spread_strike_price = round(abs(row.strike - current_price), 2)
        delta_price_premium = round(abs(row.strike - current_price + row.bid), 2)
        break_even = round(current_price - row.bid, 2)

        if isinstance(spread_bid_ask, float) and math.isnan(spread_bid_ask):
            continue

        if (isinstance(spread_strike_price, float) and math.isnan(spread_strike_price)) or \
                spread_strike_price <= config.STRIKE_PRICE_THRESHOLD:
            continue

        if isinstance(delta_price_premium, float) and math.isnan(delta_price_premium):
            continue

        est_delta = functions.estimate_delta("cc", current_price, row.strike, dte, config.RISK_FREE_RATE, row.impliedVolatility)

        option_yield = round((row.bid / current_price) * 100, 2)
        if option_yield >= config.OPTION_YIELD_THRESHOLD:
            continue

        annualized_option_yield = round(option_yield * (365 / dte), 2)
        tot_return = round(((row.strike - current_price + row.bid) / current_price) * 100, 2)
        moneyness = round(((float(row.strike) - current_price) / current_price) * 100, 2)
        sigma_distance = functions.sigma_distance_to_strike(
            current_price, float(row.strike), float(row.impliedVolatility) / 100, dte
        )

        contract = {
            "ticker": ticker.symbol,
            "exchange": exchange,
            "contract": row.contractSymbol,
            "expiry_date": option_date,
            "days_to_expiration": dte,
            "current_price": current_price,
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
            "open_interest": int(functions.normalize_nullable_fields(row.openInterest)),
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
