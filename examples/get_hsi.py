#!/usr/bin/python3 -u

import msfinance as msf

proxy = 'socks5://127.0.0.1:1088'

stock = msf.Stock(
    debug=True, 
    session='hsi.db3',
    proxy=proxy,
)

tickers_list = stock.get_hsi_tickers()

for ticker in sorted(tickers_list):
    valuations = stock.get_valuations(ticker, 'xhkg')
    financials = stock.get_financials(ticker, 'xhkg')

    print(f"Ticker: {ticker}")
    for valuation in valuations:
        print(valuation)
    for financial in financials:
        print(financial)

