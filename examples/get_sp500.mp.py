#!/usr/bin/python3 -u

import msfinance as msf
from concurrent.futures import ProcessPoolExecutor, as_completed
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import math
import logging

proxy = 'socks5://127.0.0.1:1088'

# Create an engine
engine = create_engine('sqlite:///sp500.mp.db3', pool_size=5, max_overflow=10)

# Create a session factory
InitialSessionFactory = sessionmaker(bind=engine)
# Fetch tickers outside the process pool
initial_stock = msf.Stock(
    debug=False, 
    session_factory=InitialSessionFactory,
    proxy=proxy,
)

sp500_tickers = initial_stock.get_sp500_tickers()
sp500_tickers = sorted(sp500_tickers)

tickers_list = {}
tickers_list['xnas'] = initial_stock.get_xnas_tickers()
tickers_list['xnys'] = initial_stock.get_xnys_tickers()
tickers_list['xase'] = initial_stock.get_xase_tickers()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(processName)s - %(levelname)s - %(message)s')

def process_tickers(tickers, proxy):

    SessionFactory = sessionmaker(bind=engine)
    # Create a Stock instance using the session
    stock = msf.Stock(
        debug=True, 
        session_factory=SessionFactory,
        proxy=proxy,
    )


    logging.info(f"Processing tickers: {tickers}")
    
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

    stock.driver.quit()
    return results
# End of process_tickers

def initializer():
    """ensure the parent proc's database connections are not touched
    in the new connection pool"""
    engine.dispose(close=False

# Use ProcessPoolExecutor to process tickers i parallel
max_workers = 4  # Adjust max_workers as needed
chunk_size = 8
ticker_chunks = [sp500_tickers[i:i + chunk_size] for i in range(0, len(sp500_tickers), chunk_size)]

with ProcessPoolExecutor(max_workers=max_workers, initializer=initializer) as executor:
    futures = {executor.submit(process_tickers, chunk, proxy): chunk for chunk in ticker_chunks}
    for future in as_completed(futures):
        results = future.result()
        for ticker_info, valuations, financials in results:
            print(ticker_info)
            if valuations and financials:
                for valuation in valuations:
                    print(valuation)
                for financial in financials:
                    print(financial)










