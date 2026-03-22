import yfinance
import Assets
from typing import Any
import config


def scan_covered_calls(
    ticker: Assets.Equity,
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
        cc = stock.option_chain(option_date).calls
    except Exception as e:
        # log and return empty list
        return []

    if cc is None or cc.empty:
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

        for row in cc.itertuples(index=False):
            if row.bid < threshold_bid or row.strike <= current_price:
                continue

            spread_bid_ask = round(row.ask - row.bid, 2)
            spread_strike_price = round(row.strike - current_price, 2)
            delta_price_premium = round(row.strike - current_price + row.bid, 2)
            ratio_bid_strike = round((row.bid / row.strike) * 100, 2)

            contract = {
                "symbol": ticker.symbol,
                "contract": row.contractSymbol,
                "strike_date": option_date,
                "current_price": current_price,
                "rel_std_deviation": rel_std_deviation,
                "spread_premium_price_and_bid": round(float(delta_price_premium), 2),
                "spread_strike_price": round(float(spread_strike_price), 2),
                "strike_price": round(float(row.strike), 2),
                "bid_per_share": round(float(row.bid), 2),
                "premium_per_contract": round(float(row.bid * 100), 2),
                "spread_bid_ask": round(float(spread_bid_ask), 2),
                "open_interest": row.openInterest,
                "impl_volatility": round(float(row.impliedVolatility * 100), 2),
                "ratio_bid_strike": ratio_bid_strike,
                "sector": sector,
                "industry": industry,
                "highest_price": highest_price,
                "avg_price": avg_price,
                "lowest_price": lowest_price,
                "main_trend": main_trend,
                "beta": beta,
            }

            # all_contracts.append(contract[cc_contract.iloc[i]])
            matched_contracts.append(contract)

    return matched_contracts


def scan_etf_covered_calls(
    ticker: Assets.ETF,
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
        cc = stock.option_chain(option_date).calls
    except Exception as e:
        # log and return empty list
        return []

    if cc is None or cc.empty:
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

        for row in cc.itertuples(index=False):
            if row.bid < threshold_bid or row.strike <= current_price:
                continue

            spread_bid_ask = round(row.ask - row.bid, 2)
            spread_strike_price = round(row.strike - current_price, 2)
            delta_price_premium = round(row.strike - current_price + row.bid, 2)
            ratio_bid_strike = round((row.bid / row.strike) * 100, 2)

            contract = {
                "symbol": ticker.symbol,
                "contract": row.contractSymbol,
                "strike_date": option_date,
                "current_price": current_price,
                "rel_std_deviation": rel_std_deviation,
                "spread_premium_price_and_bid": round(float(delta_price_premium), 2),
                "spread_strike_price": round(float(spread_strike_price), 2),
                "strike_price": round(float(row.strike), 2),
                "bid_per_share": round(float(row.bid), 2),
                "premium_per_contract": round(float(row.bid * 100), 2),
                "spread_bid_ask": round(float(spread_bid_ask), 2),
                "open_interest": row.openInterest,
                "impl_volatility": round(float(row.impliedVolatility * 100), 2),
                "ratio_bid_strike": ratio_bid_strike,
                "highest_price": highest_price,
                "avg_price": avg_price,
                "lowest_price": lowest_price,
                "main_trend": main_trend,
            }

            matched_contracts.append(contract)

    return matched_contracts





if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")

