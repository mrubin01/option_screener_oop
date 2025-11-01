import sys
import time
import functions
import warnings
import pandas as pd
from datetime import datetime
import Assets
import yfinance as yf

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

user_agent = functions.create_user_agent()

# empty the cache only the first run of the day
CLEAR_CACHE = False
if CLEAR_CACHE:
    user_agent.cache.clear()

TYPE = 0  # 0 call, 1 put, 2 spread
STOCK_EXCHANGE = 1
EXCHANGES = ["NYSE", "NASDAQ", "ARCA"]
SCOPE = 0  # 0 only tickers with options, 1 whole ticker list
WRITE_TICKERS_TO_FILE = 0
MIN_BID_PRICE = 0.2
TREND = 0  # -1 no trend, 0 downtrend, 1 uptrend
HAVE_OPTIONS = 0  # 0 no active options, 1 with active options
MAX_STOCK_PRICE = 1000
YEAR, MONTH, DAY = 2025, 11, [21, 28]

ticker_list = ["BYND", "JBLU", "AUR"]
tickers_with_options = []
best_tickers_with_options = []
best_contracts_dict = {}

if STOCK_EXCHANGE in [0, 1]:
    for t in ticker_list:
        ticker = Assets.Equity(t, EXCHANGES[1])
        stock, price, options, sector, industry, beta, vol_aver_10days, vol_aver_3months = ticker.get_info()
        if len(options) > 0 and price <= MAX_STOCK_PRICE:
            if t not in tickers_with_options:
                tickers_with_options.append(t)

            price_data = ticker.get_high_low_price()
            lowest_price, highest_price, first_price, last_price = price_data[0], price_data[1], price_data[2], price_data[3]
            avg_price, avg_price_7d, avg_price_30d = price_data[4], price_data[5], price_data[6]
            trend = price_data[7]
            abs_std_deviation, rel_std_deviation = price_data[8], price_data[9]
            lowest_decrease = round((lowest_price / price) * 100, 2)
            highest_increase = round((highest_price / price) * 100, 2)

            for d in options:
                new_date = datetime.strptime(d, "%Y-%m-%d")
                day = new_date.day
                month = new_date.month
                year = new_date.year

                if year == YEAR and month == MONTH and day in DAY and TYPE == 0:
                    try:
                        cc = stock.option_chain(d).calls

                        if cc is not None:
                            cc_contract = cc["contractSymbol"]
                            cc_strike = cc["strike"]
                            cc_bid = cc["bid"]
                            cc_ask = cc["ask"]
                            cc_vol = cc["volume"]
                            cc_open_interest = cc["openInterest"]
                            cc_impl_volatility = round(cc["impliedVolatility"] * 100, 2)

                            for i in range(len(cc_contract)):
                                spread_bid_ask = round(cc_ask[i] - cc_bid[i], 2)
                                spread_strike_price = round(cc_strike[i] - price, 2)
                                delta_price_premium = round(cc_strike[i] - price + cc_bid[i], 2)
                                ratio_bid_price = round((cc_bid[i] / price) * 100, 2)
                                price_vs_avgs = -1
                                if price < avg_price and price < avg_price_7d and price < avg_price_30d:
                                    price_vs_avgs = 1  # price is lower than the averages

                                if TREND == 0:
                                    if cc_bid[i] >= MIN_BID_PRICE and cc_strike[i] < price and price_vs_avgs == 1:
                                        if t not in best_tickers_with_options:
                                            best_tickers_with_options.append(t)

                                        best_contracts_dict[cc_contract[i]] = [cc_contract[i], d, t, price, round(float(delta_price_premium), 2),
                                                                               round(float(spread_strike_price), 2), round(float(cc_strike[i]), 2),
                                                                                round(float(cc_bid[i] * 100), 2), cc_open_interest[i],
                                                                                cc_impl_volatility[i], ratio_bid_price, sector, industry,
                                                                                highest_price, avg_price, lowest_price, beta]

                                        print(best_contracts_dict.values())

                                elif TREND == 1:
                                    pass


                    except Exception as e:
                        continue

                elif year == YEAR and month == MONTH and day in DAY and TYPE == 1:
                    pass
                elif year == YEAR and month == MONTH and day in DAY and TYPE == 2:
                    pass

        else:
            pass




elif STOCK_EXCHANGE == 2:
    pass

