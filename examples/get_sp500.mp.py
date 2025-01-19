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


def setup_logging():
    logger = logging.getLogger()
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(processName)s:%(levelname)s:%(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger

def process_tickers(tickers, proxy):
    logger = setup_logging()  # Setup logging for each process

    SessionFactory = sessionmaker(bind=engine)
    # Create a Stock instance using the session
    stock = msf.Stock(
        debug=True,
        session_factory=SessionFactory,
        proxy=proxy,
    )

    logger.info(f"Processing tickers: {tickers}")

    results = []
    for ticker in tickers:
        if ticker in tickers_list['xnas']:
            key_metrics = stock.get_key_metrics(ticker, 'xnas')
            financials = stock.get_financials(ticker, 'xnas', stage='Restated')
        elif ticker in tickers_list['xnys']:
            key_metrics = stock.get_key_metrics(ticker, 'xnys')
            financials = stock.get_financials(ticker, 'xnys', stage='Restated')
        elif ticker in tickers_list['xase']:
            key_metrics = stock.get_key_metrics(ticker, 'xase')
            financials = stock.get_financials(ticker, 'xase', stage='Restated')
        else:
            results.append((f"Ticker: {ticker} is not found in any exchange", None, None))
            continue

        results.append((f"Ticker: {ticker}", key_metrics, financials))

    stock.driver.quit()
    return results
# End of process_tickers

def initializer():
    """ensure the parent proc's database connections are not touched
    in the new connection pool"""
    engine.dispose(close=False)

# Use ProcessPoolExecutor to process tickers in parallel
max_workers = 4  # Adjust max_workers as needed
chunk_size = 16
ticker_chunks = [sp500_tickers[i:i + chunk_size] for i in range(0, len(sp500_tickers), chunk_size)]

with ProcessPoolExecutor(max_workers=max_workers, initializer=initializer) as executor:
    futures = {executor.submit(process_tickers, chunk, proxy): chunk for chunk in ticker_chunks}
    for future in as_completed(futures):
        results = future.result()
        for ticker_info, key_metrics, financials in results:
            print(ticker_info)
            if key_metrics and financials:
                for key_metric in key_metrics:
                    print(key_metric)
                for financial in financials:
                    print(financial)










