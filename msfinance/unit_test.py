#!/usr/bin/python3 -u

import os
import time
import re
import sys
import stocks
import pandas as pd
import requests
import json


proxy = 'socks5://127.0.0.1:1088'

stock = stocks.Stock(
    debug=True, 
    session='/tmp/msfinance/msf.sql3',
    proxy=proxy,
)


tickers_list = {}
tickers_list['xnas'] = stock.get_xnas_tickers()
tickers_list['xnys'] = stock.get_xnys_tickers()
tickers_list['xase'] = stock.get_xase_tickers()

sp500_tickers = stock.get_sp500_tickers()

# Test method in class Stock
stock.get_income_statement('aapl', 'xnas')
stock.get_balance_sheet_statement('aapl', 'xnas')
stock.get_cash_flow_statement('aapl', 'xnas')

stock.get_growth('aapl', 'xnas')
stock.get_operating_and_efficiency('aapl', 'xnas')
stock.get_financial_health('aapl', 'xnas')
stock.get_cash_flow('aapl', 'xnas')

