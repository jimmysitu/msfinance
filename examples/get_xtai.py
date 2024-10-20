#!/usr/bin/python3 -u

import msfinance as msf

proxy = 'socks5://127.0.0.1:1088'

stock = msf.Stock(
    debug=True,
    browser='chrome',
    database='xtai.db3',
    proxy=proxy,
)

tickers_list = {
    '2454',
    '2330',  # TSMC
}

for ticker in sorted(tickers_list):
    valuations = stock.get_valuations(ticker, 'xtai')
    financials = stock.get_financials(ticker, 'xtai')

    print(f"Ticker: {ticker}")
    for valuation in valuations:
        print(valuation)
    for financial in financials:
        print(financial)
