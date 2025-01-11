#!/usr/bin/python3 -u

import msfinance as msf

proxy = 'socks5://127.0.0.1:1088'

stock = msf.Stock(
    debug=True,
    database='xnas.db3',
    proxy=proxy,
)

tickers_list = {
    'asml', # ASML Holding NV ADR
}

for ticker in sorted(tickers_list):
    key_metrics = stock.get_key_metrics(ticker, 'xnas')
    financials = stock.get_financials(ticker, 'xnas')

    print(f"Ticker: {ticker}")
    for key_metric in key_metrics:
        print(key_metric)
    for financial in financials:
        print(financial)
