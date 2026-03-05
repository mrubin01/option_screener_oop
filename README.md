# option_screener_oop

Relative standard deviation or Coefficient of variation (CoV) measures the deviation between the historical mean 
price and the current price performance of a financial asset. In short, it measures its volatility
The formula is (std_dev / mean price) * 100

CoV < 2 LOW, CoV < 5 MODERATE, CoV >= 5 HIGH, CoV >= 10 VERY HIGH

It seems that, for the spread options in ARCA, the best contracts are those with a CoV < 10%. A CoV < 10% 
means low volatility. However, a value below 10% restrict the number of contracts that will be selected

