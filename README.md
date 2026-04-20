## option_screener_oop

Relative standard deviation or Coefficient of variation (CoV) measures the deviation between the historical mean 
price and the current price performance of a financial asset. In short, it measures its volatility
The formula is (std_dev / mean price) * 100

CoV < 2 LOW, CoV < 5 MODERATE, CoV >= 5 HIGH, CoV >= 10 VERY HIGH

A CoV < 5% means low volatility. However, a value below 10% restrict the number of contracts that will be selected

### main()  
In the main for the object ticker, equity or ETF, there are four checks: price data, price stats, standard deviation vs threshold  
and price vs threshold. This happens before calling the option function: if any of these checks is negative,  
the loop will continue with the following ticker  

Fields:
"ticker",
"exchange",
"contract",
"expiry_date",
"current_price",
"rel_std_deviation",
"spread_premium_price_and_bid",
"spread_strike_price",
"strike_price",
"bid_per_share",
"premium_per_contract",
"spread_bid_ask",
"open_interest",
"impl_volatility",
"ratio_bid_strike",
"sector"                        -> nullable,
"industry"                      -> nullable,
"highest_price",
"avg_price",
"lowest_price",
"main_trend",
"beta"                          -> nullable

### Covered calls
If the function completes, it will return a dictionary with 21 (equity) or 18 (ETF) items  

### Put options  


### Spread options  
