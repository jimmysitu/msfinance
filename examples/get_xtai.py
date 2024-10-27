#!/usr/bin/python3 -u

import msfinance as msf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

proxy = 'socks5://127.0.0.1:1088'

# Create a shared SQLAlchemy engine and session factory
engine = create_engine('sqlite:///xtai.db3', pool_size=5, max_overflow=10)
SessionFactory = sessionmaker(bind=engine)

stock = msf.Stock(
    debug=True,
    session_factory=SessionFactory,
    proxy=proxy,
)

tickers_list = {
    '2454',  # Mediatek
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
