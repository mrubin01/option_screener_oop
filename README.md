## option_screener_oop

Relative standard deviation or Coefficient of variation (CoV) measures the deviation between the historical mean 
price and the current price performance of a financial asset. In short, it measures its volatility
The formula is (std_dev / mean price) * 100

CoV < 2 LOW, CoV < 5 MODERATE, CoV >= 5 HIGH, CoV >= 10 VERY HIGH

A CoV < 5% means low volatility. However, a value below 10% restrict the number of contracts that will be selected

Moneyness or OTM distance is the % the stock needs to drop (puts) or to rise (calls, spreads) to reach the strike  

Sigma Distance to strike in volatility units: how many implied STD_DEV the current price is away from the option’s strike 
over the remaining DTE to avoid assignment; the higher the SD, the better: 0-0.5 very close, 0.5-1 close, 1-1.5 moderate, 
1.5-2.0 high, 2-3.0 very high

### main()  
In the main for the object ticker, equity or ETF, there are four checks: price data, price stats, standard deviation vs threshold  
and price vs threshold. This happens before calling the option function: if the code is not stopped by these checks,  
the loop will continue with the following ticker  

Fields:
"ticker"
"exchange"
"contract"
"expiry_date"
"days_to_expiration"			
"current_price"
"strike_price"
"moneyness"
"sigma_distance"
"otm"
"coeff_variation"	
"max_profit"			
"max_profit_per_contract"
"bid_per_share"
"premium_per_contract"
"option_yield"				pivot
"roc"
"spread_bid_ask"
"break_even"
"open_interest"				nullable
"impl_volatility"		
"tot_return"
"delta"
"sector"				    nullable
"industry"				    nullable
"highest_price"
"avg_price"
"lowest_price"
"main_trend"
"beta"					    nullable

Each of the three modules covered_calls.py, put_options.py, spread_options.py will return a dictionary with 30 (equity) or 
27 (ETF) items. 

### Covered calls
The function will return a list containing a dictionary for every contract that has passed the following filters:
1. spread_bid_ask, spread_strike_price, delta_price_premium and option_yield must not be empty or null
2. the bid per share (premium) must be equal or higher than the MIN_BID_PRICE;
3. the strike price must be higher than the current_price
4. spread_strike_price must be below 20;
5. option_yield must be below 25

### Put options  
The function will return a list containing a dictionary for every contract that has passed the following filters:
1. spread_bid_ask, spread_strike_price, delta_price_premium and option_yield must not be empty or null
2. the bid per share (premium) must be equal or higher than the MIN_BID_PRICE;
3. the strike price must be lower than the current_price --> different from cov calls
4. spread_strike_price must be below 20;
5. option_yield must be below 25

Some metrics have different formulas compared to covered calls:  
max_profit, max_profit_per_contract  
option_yield, roc  
tot_return
moneyness


### Spread options  
Spread options are actually covered calls, but with additional filters: 1 they must be weekly; 2 they must have a  
spread between the current price and the strike price of at least 1.5; 3 they must have good short calls as well as 
good long calls having an expiration date after at least 3 months
