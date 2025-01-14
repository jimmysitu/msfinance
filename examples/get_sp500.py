#!/usr/bin/python3 -u

import msfinance as msf

proxy = 'socks5://127.0.0.1:1088'

stock = msf.Stock(
    debug=True, 
    database='sp500.db3',
    proxy=proxy,
)

sp500_tickers = stock.get_sp500_tickers()

tickers_list = {}
tickers_list['xnas'] = stock.get_xnas_tickers()
tickers_list['xnys'] = stock.get_xnys_tickers()
tickers_list['xase'] = stock.get_xase_tickers()

for ticker in sorted(sp500_tickers):
    if ticker in tickers_list['xnas']:
        key_metrics = stock.get_key_metrics(ticker, 'xnas')
        financials = stock.get_financials(ticker, 'xnas')
    elif ticker in tickers_list['xnys']:
        key_metrics = stock.get_key_metrics(ticker, 'xnys')
        financials = stock.get_financials(ticker, 'xnys')
    elif ticker in tickers_list['xase']:
        key_metrics = stock.get_key_metrics(ticker, 'xase')
        financials = stock.get_financials(ticker, 'xase')
    else:
        print(f"Ticker: {ticker} is not found in any exchange")

    print(f"Ticker: {ticker}")
    for key_metric in key_metrics:
        print(key_metric)
    for financial in financials:
        print(financial)
