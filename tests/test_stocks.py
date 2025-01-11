#!/usr/bin/python3 -u

import tempfile
import sqlite3
from msfinance import stocks
import os
import logging
import pandas as pd

from selenium import webdriver
import undetected_chromedriver as uc

# For Chrome driver
from webdriver_manager.chrome import ChromeDriverManager

# For Firefox driver
from webdriver_manager.firefox import GeckoDriverManager

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# It seems that undetected_chromedriver is not working properly, when user_multi_procs is set to True
# So let user_multi_procs to be False here to initialize the driver environment
nouse_driver = uc.Chrome(
    browser_executable_path=os.environ.get('CHROME_PATH'),
    headless=True,
    debug=True,
    version_main=126,
    use_subprocess=False,
    user_multi_procs=False,
    service=webdriver.ChromeService(ChromeDriverManager(driver_version='126').install()),
)

def test_stocks():
    logging.info("Starting test_stocks")

    proxy = 'socks5://127.0.0.1:1088'
    database = os.path.join(tempfile.gettempdir(), 'msfinance', 'msf.db3')
    logging.debug(f"Database session path: {database}")

    if 'true' == os.getenv('GITHUB_ACTIONS'):
        logging.info("Running in GitHub Actions environment")
        stock = stocks.Stock(
            debug=False,
            database=database,
            proxy=None,
        )
    else:
        logging.info("Running in local environment")
        stock = stocks.Stock(
            debug=False,
            database=database,
            proxy=proxy,
        )

    tickers_list = {}
    tickers_list['xnas'] = stock.get_xnas_tickers()
    logging.debug(f"XNAS tickers: {tickers_list['xnas']}")
    tickers_list['xnys'] = stock.get_xnys_tickers()
    logging.debug(f"XNYS tickers: {tickers_list['xnys']}")
    tickers_list['xase'] = stock.get_xase_tickers()
    logging.debug(f"XASE tickers: {tickers_list['xase']}")

    sp500_tickers = stock.get_sp500_tickers()
    logging.debug(f"S&P 500 tickers: {sp500_tickers}")
    assert 'AAPL' in sp500_tickers, "AAPL not found in S&P 500 tickers"

    hsi_tickers = stock.get_hsi_tickers()
    logging.debug(f"HSI tickers: {hsi_tickers}")
    assert '00700' in hsi_tickers, "00700 not found in HSI tickers"

    # Test method in class Stock
    stage = 'As Originally Reported'
    logging.info(f"Testing financial statements for stage: {stage}")
    stock.get_income_statement('aapl', 'xnas', stage=stage)
    stock.get_balance_sheet_statement('aapl', 'xnas', stage=stage)
    stock.get_cash_flow_statement('aapl', 'xnas', stage=stage)

    stock.get_financial_summary('aapl', 'xnas')
    stock.get_growth('aapl', 'xnas')
    stock.get_profitability_and_efficiency('aapl', 'xnas')
    stock.get_financial_health('aapl', 'xnas')
    stock.get_cash_flow('aapl', 'xnas')

    db = sqlite3.connect(database)
    logging.info("Connected to the database")

    for exchange in ['nasdaq', 'nyse', 'amex']:
        query = f"SELECT * FROM us_exchange_{exchange}_tickers"
        logging.debug(f"Executing query: {query}")
        df = pd.read_sql_query(query, db)
        assert df is not None, f"{query} is not found in database"

    stage = 'As Originally Reported'.replace(' ', '_').lower()
    for statement in ['income_statement', 'balance_sheet', 'cash_flow']:
        query = f"SELECT * FROM aapl_xnas_{statement}_annual_{stage}"
        logging.debug(f"Executing query: {query}")
        df = pd.read_sql_query(query, db)
        assert df is not None, f"{query} is not found in database"

    for statistics in ['financial_summary', 'growth', 'profitability_and_efficiency', 'financial_health', 'cash_flow']:
        query = f"SELECT * FROM aapl_xnas_{statistics}"
        logging.debug(f"Executing query: {query}")
        df = pd.read_sql_query(query, db)
        assert df is not None, f"{query} is not found in database"

    logging.info("test_stocks completed successfully")
