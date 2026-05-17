import yfinance
import Assets
from typing import Any
import config
import math
import functions


def scan_put_options(
    ticker: Assets.Equity,
    exchange: str,
    option_date: str,
    threshold_bid: float,
    stock: yfinance.Ticker,
    current_price: float,
    sector: str,
    industry: str,
    beta: float,
    lowest_price: float,
    highest_price: float,
    avg_price: float,
    avg_price_7d: float,
    avg_price_30d: float,
    trend: int,
    rel_std_deviation: float
) -> list[dict[str, Any]]:

    matched_contracts = []

    if threshold_bid < 0:
        raise ValueError("threshold_bid must be non-negative")

    try:
        puts = stock.option_chain(option_date).puts
    except Exception as e:
        # log and return empty list
        return []

    if puts is None or puts.empty:
        return []
    else:
        # compare the current price with all averages
        below_all_avgs = current_price < avg_price and current_price < avg_price_7d and current_price < avg_price_30d
        above_all_avgs = current_price > avg_price and current_price > avg_price_7d and current_price > avg_price_30d

        price_vs_avgs = -1
        if below_all_avgs:
            price_vs_avgs = 0  # price is lower than the averages
        elif above_all_avgs:
            price_vs_avgs = 1  # price is higher than the averages

        # main_trend
        main_trend = config.TREND_SIDEWAYS
        if price_vs_avgs == 1 and trend == 1:
            main_trend = config.TREND_UP
        elif price_vs_avgs == 0 and trend == 0:
            main_trend = config.TREND_DOWN

        for row in puts.itertuples(index=False):
            if row.bid is None or row.bid == "" or (isinstance(row.bid, float) and math.isnan(row.bid)):
                continue

            if row.bid < threshold_bid or row.strike >= current_price:
                continue

            spread_bid_ask = round(row.ask - row.bid, 2)
            spread_strike_price = round(abs(row.strike - current_price), 2)
            delta_price_premium = row.bid   # different from cov calls
            break_even = round(current_price - row.bid, 2)

            if spread_bid_ask is None or spread_bid_ask == "" or (isinstance(spread_bid_ask, float) and math.isnan(spread_bid_ask)):
                continue

            if spread_strike_price is None or \
                    spread_strike_price == "" or \
                    (isinstance(spread_strike_price, float) and math.isnan(spread_strike_price)) or \
                    spread_strike_price <= config.STRIKE_PRICE_THRESHOLD:
                continue

            if delta_price_premium is None or delta_price_premium == "" or (isinstance(delta_price_premium, float) and math.isnan(delta_price_premium)):
                continue

            days_to_expiration = functions.days_to_expiration(option_date)
            est_delta = functions.estimate_delta("put", current_price, row.strike, days_to_expiration, config.RISK_FREE_RATE, row.impliedVolatility)

            option_yield = round((row.bid / row.strike) * 100, 2)
            annualized_option_yield = round(option_yield * (365 / days_to_expiration), 2)
            tot_return = round((row.bid / current_price) * 100, 2)

            # new metrics
            moneyness = round(((current_price - float(row.strike)) / current_price) * 100, 2)
            sigma_distance = functions.sigma_distance_to_strike(
                current_price,
                float(row.strike),
                float(row.impliedVolatility) / 100,
                days_to_expiration
            )

            if option_yield is None or \
                    option_yield == "" or \
                    option_yield >= config.OPTION_YIELD_THRESHOLD or \
                    (isinstance(option_yield, float) and math.isnan(option_yield)):
                continue

            contract = {
                "ticker": ticker.symbol,
                "exchange": exchange,
                "contract": row.contractSymbol,
                "expiry_date": option_date,
                "days_to_expiration": days_to_expiration,
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
                "open_interest": functions.normalize_nullable_fields(row.openInterest),
                "impl_volatility": round(float(row.impliedVolatility * 100), 2),
                "option_yield": option_yield,
                "roc": annualized_option_yield,
                "tot_return": tot_return,
                "delta": est_delta,
                "sector": sector,
                "industry": industry,
                "highest_price": highest_price,
                "avg_price": avg_price,
                "lowest_price": lowest_price,
                "main_trend": main_trend,
                "beta": beta,
            }

            matched_contracts.append(contract)

    return matched_contracts


def scan_etf_put_options(
        ticker: Assets.ETF,
        exchange: str,
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
        rel_std_deviation: float
) -> list[dict[str, Any]]:

    matched_contracts = []

    if threshold_bid < 0:
        raise ValueError("threshold_bid must be non-negative")

    try:
        puts = stock.option_chain(option_date).puts
    except Exception as e:
        # log and return empty list
        return []

    if puts is None or puts.empty:
        return []
    else:
        # compare the current price with all averages
        below_all_avgs = current_price < avg_price and current_price < avg_price_7d and current_price < avg_price_30d
        above_all_avgs = current_price > avg_price and current_price > avg_price_7d and current_price > avg_price_30d

        price_vs_avgs = -1
        if below_all_avgs:
            price_vs_avgs = 0  # price is lower than the averages
        elif above_all_avgs:
            price_vs_avgs = 1  # price is higher than the averages

        # main_trend
        main_trend = config.TREND_SIDEWAYS
        if price_vs_avgs == 1 and trend == 1:
            main_trend = config.TREND_UP
        elif price_vs_avgs == 0 and trend == 0:
            main_trend = config.TREND_DOWN

        for row in puts.itertuples(index=False):
            if row.bid is None or row.bid == "" or (isinstance(row.bid, float) and math.isnan(row.bid)):
                continue

            if row.bid < threshold_bid or row.strike >= current_price:
                continue

            spread_bid_ask = round(row.ask - row.bid, 2)
            spread_strike_price = round(abs(row.strike - current_price), 2)
            delta_price_premium = row.bid  # different from cov calls
            break_even = round(current_price - row.bid, 2)

            if spread_bid_ask is None or spread_bid_ask == "" or (isinstance(spread_bid_ask, float) and math.isnan(spread_bid_ask)):
                continue

            if spread_strike_price is None or \
                    spread_strike_price == "" or \
                    (isinstance(spread_strike_price, float) and math.isnan(spread_strike_price)) or \
                    spread_strike_price <= config.STRIKE_PRICE_THRESHOLD:
                continue

            if delta_price_premium is None or delta_price_premium == "" or (isinstance(delta_price_premium, float) and math.isnan(delta_price_premium)):
                continue

            days_to_expiration = functions.days_to_expiration(option_date)
            est_delta = functions.estimate_delta("put", current_price, row.strike, days_to_expiration, config.RISK_FREE_RATE, row.impliedVolatility)

            option_yield = round((row.bid / row.strike) * 100, 2)
            annualized_option_yield = round(option_yield * (365 / days_to_expiration), 2)
            tot_return = round((row.bid / current_price) * 100, 2)

            # new metrics
            moneyness = round(((current_price - float(row.strike)) / current_price) * 100, 2)
            sigma_distance = functions.sigma_distance_to_strike(
                current_price,
                float(row.strike),
                float(row.impliedVolatility) / 100,
                days_to_expiration
            )

            if option_yield is None or \
                    option_yield == "" or \
                    option_yield >= config.OPTION_YIELD_THRESHOLD or \
                    (isinstance(option_yield, float) and math.isnan(option_yield)):
                continue

            contract = {
                "ticker": ticker.symbol,
                "exchange": exchange,
                "contract": row.contractSymbol,
                "expiry_date": option_date,
                "days_to_expiration": days_to_expiration,
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
                "open_interest": functions.normalize_nullable_fields(row.openInterest),
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

            matched_contracts.append(contract)

    return matched_contracts


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")
