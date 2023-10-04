#!/usr/bin/python3 -u

import os
import time
import re
import sys
import stocks
import pandas as pd
import requests

proxy = 'socks5://127.0.0.1:1088'
print(re.split(r'://|:', proxy))

stock = stocks.Stock(
    debug=True, 
    session='/tmp/msfinance/msf.sql3',
    proxy=proxy,
)

#stock.get_income_statement('aapl', 'xnas')
#stock.get_balance_sheet_statement('aapl', 'xnas')
#stock.get_cash_flow_statement('aapl', 'xnas')
#
#stock.get_growth('aapl', 'xnas')
#stock.get_operating_and_efficiency('aapl', 'xnas')
#stock.get_financial_health('aapl', 'xnas')
print(stock.get_cash_flow('aapl', 'xnas'))

sp500_tickers = stock.get_sp500_tickers()


## You can print the list of S&P 500 stock symbols
print(sp500_tickers)

for ticker in sp500_tickers:
    pass




