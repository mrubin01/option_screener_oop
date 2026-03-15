import warnings
import pandas as pd
import Assets
from typing import Any


warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)


def run(
    ticker: Assets.Equity,
    option_date: str,
    threshold_bid: float,
    rel_std_deviation: float,
    std_dev_threshold: float,
) -> list[dict[str, Any]]:

    data = ticker.get_info()
    if not data:
        return

    stock = data["stock"]
    current_price = data["price"]
    options = data["options"]
    sector = data["sector"]
    industry = data["industry"]
    beta = data["beta"]
    vol_aver_10days = data["vol_aver_10days"]
    vol_aver_3months = data["vol_aver_3months"]

    price_data = ticker.get_high_low_price()
    lowest_price, highest_price, first_price, last_price = price_data[0], price_data[1], price_data[2], price_data[3]
    avg_price, avg_price_7d, avg_price_30d = price_data[4], price_data[5], price_data[6]
    trend = price_data[7]

    cc = stock.option_chain(option_date).calls

    contract = {}
    all_contracts = []

    if cc is not None:
        cc_contract = cc["contractSymbol"]
        cc_strike = cc["strike"]
        cc_bid = cc["bid"]
        cc_ask = cc["ask"]
        cc_open_interest = cc["openInterest"]
        cc_impl_volatility = round(cc["impliedVolatility"] * 100, 2)

        for i in range(len(cc_contract)):
            spread_bid_ask = round(cc_ask[i] - cc_bid[i], 2)
            spread_strike_price = round(cc_strike[i] - current_price, 2)
            delta_price_premium = round(cc_strike[i] - current_price + cc_bid[i], 2)
            ratio_bid_strike = round((cc_bid[i] / cc_strike[i]) * 100, 2)
            price_vs_avgs = -1
            if current_price < avg_price and current_price < avg_price_7d and current_price < avg_price_30d:
                price_vs_avgs = 0  # price is lower than the averages
            if current_price > avg_price and current_price > avg_price_7d and current_price > avg_price_30d:
                price_vs_avgs = 1  # price is higher than the averages

            # main_trend
            main_trend = 0  # sideways
            if price_vs_avgs == 1 and trend == 1:
                main_trend = 1  # uptrend
            elif price_vs_avgs == 0 and trend == 0:
                main_trend = -1  # downtrend

            if cc_bid[i] >= threshold_bid and cc_strike[i] > current_price and rel_std_deviation < std_dev_threshold:
                # This must be in the main, not here
                # if ticker.symbol not in best_tickers_with_options:
                #     best_tickers_with_options.append(ticker.symbol)
                contract[cc_contract[i]] = dict(symbol=ticker.symbol,
                                                contract=cc_contract[i],
                                                strike_date=option_date,
                                                current_price=current_price,
                                                rel_std_deviation=rel_std_deviation,
                                                spread_premium_price_and_bid=round(float(delta_price_premium), 2),
                                                spread_strike_price=round(float(spread_strike_price), 2),
                                                strike_price=round(float(cc_strike[i]), 2),
                                                bid=round(float(cc_bid[i] * 100), 2),
                                                spread_bid_ask=round(float(spread_bid_ask), 2),
                                                open_interest=cc_open_interest[i],
                                                impl_volatility=cc_impl_volatility[i],
                                                ratio_bid_strike=ratio_bid_strike,  # pivot field
                                                sector=sector,
                                                industry=industry,
                                                highest_price=highest_price,
                                                avg_price=avg_price,
                                                lowest_price=lowest_price,
                                                main_trend=main_trend,
                                                beta=beta)

                all_contracts.append(contract[cc_contract[i]])

    # sort contracts based on the ratio bid/strike price
    all_contracts_sorted = sorted(all_contracts, key=lambda x: x["ratio_bid_strike"], reverse=True)

    return all_contracts_sorted


if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be run directly")

# ticker_test = Assets.Equity("AAPL", "NASDAQ")
# print(run(ticker_test, "2026-03-13", 0.3, 12.0, 15.0))
