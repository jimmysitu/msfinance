#!/usr/bin/python3 -u

import msfinance as msf
from concurrent.futures import ProcessPoolExecutor, as_completed
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import math

proxy = 'socks5://127.0.0.1:1088'

# Create a shared SQLAlchemy engine and session factory
engine = create_engine('sqlite:///sp500.db3', pool_size=5, max_overflow=10)
SessionFactory = sessionmaker(bind=engine)

# Fetch tickers outside the process pool
initial_stock = msf.Stock(
    debug=False, 
    session_factory=SessionFactory,
    proxy=proxy,
)

sp500_tickers = initial_stock.get_sp500_tickers()

tickers_list = {}
tickers_list['xnas'] = initial_stock.get_xnas_tickers()
tickers_list['xnys'] = initial_stock.get_xnys_tickers()
tickers_list['xase'] = initial_stock.get_xase_tickers()

def process_tickers(tickers, proxy, session_factory):
    # Create a single Stock instance for each process
    stock = msf.Stock(
        debug=True, 
        session_factory=session_factory,
        proxy=proxy,
    )

    results = []
    for ticker in tickers:
        if ticker in tickers_list['xnas']:
            valuations = stock.get_valuations(ticker, 'xnas')
            financials = stock.get_financials(ticker, 'xnas')
        elif ticker in tickers_list['xnys']:
            valuations = stock.get_valuations(ticker, 'xnys')
            financials = stock.get_financials(ticker, 'xnys')
        elif ticker in tickers_list['xase']:
            valuations = stock.get_valuations(ticker, 'xase')
            financials = stock.get_financials(ticker, 'xase')
        else:
            results.append((f"Ticker: {ticker} is not found in any exchange", None, None))
            continue

        results.append((f"Ticker: {ticker}", valuations, financials))
    
    return results

# Use ProcessPoolExecutor to process tickers in parallel
max_workers = 3  # Adjust max_workers as needed
chunk_size = math.ceil(len(sp500_tickers) / max_workers)
ticker_chunks = [sp500_tickers[i:i + chunk_size] for i in range(0, len(sp500_tickers), chunk_size)]

with ProcessPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(process_tickers, chunk, proxy, SessionFactory): chunk for chunk in ticker_chunks}
    for future in as_completed(futures):
        results = future.result()
        for ticker_info, valuations, financials in results:
            print(ticker_info)
            if valuations and financials:
                for valuation in valuations:
                    print(valuation)
                for financial in financials:
                    print(financial)










