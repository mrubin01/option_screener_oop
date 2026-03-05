import sys
import time
import functions
import warnings
import pandas as pd
from datetime import datetime
import csv
import Assets
import config

warnings.simplefilter("ignore")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)


def run(year_short: int, month_short: list, day_short: list, exchange: int, tickers: list):
    if not isinstance(year_short, int) or \
            not isinstance(month_short, list) or \
            not isinstance(day_short, list) or \
            not isinstance(tickers, list):
        print("Something is wrong with the parameters!")
        sys.exit()

    print(f"|-- Scanning the best short covered calls in {exchange} --|")

    for t in tickers:
        pass
