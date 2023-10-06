#!/usr/bin/python3 -u

import pandas as pd
import os

import msfinance as msf



proxy = 'socks5://127.0.0.1:1088'

stock = msf.Stock(
    debug=True, 
    session='sp500.sql3',
    proxy=proxy,
)

sp500_tickers = stock.get_sp500_tickers()

tickers_list = {}
tickers_list['xnas'] = stock.get_xnas_tickers()
tickers_list['xnys'] = stock.get_xnys_tickers()
tickers_list['xase'] = stock.get_xase_tickers()

for ticker in sorted(sp500_tickers):
    if ticker in tickers_list['xnas']:
        valuations = stock.get_valuations(ticker, 'xnas')
    elif ticker in tickers_list['xnys']:
        valuations = stock.get_valuations(ticker, 'xnys')
    elif ticker in tickers_list['xase']:
        valuations = stock.get_valuations(ticker, 'xnys')
    else:
        print(f"Ticker: {ticker} is not found in any exchange")

    for valuation in valuations:
        print(f"Ticker: {ticker}")
        print(valuation)

