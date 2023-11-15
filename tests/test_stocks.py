#!/usr/bin/python3 -u

import sqlite3
from msfinance import stocks
import os
import time
import re
import sys
import pandas as pd
import requests
import json

def test_stocks():
    proxy = 'socks5://127.0.0.1:1088'
    session='/tmp/msfinance/msf.sql3'


    if 'true' == os.getenv('GITHUB_ACTIONS'):
        stock = stocks.Stock(
            debug=False,
            session=session,
            proxy=None,
        )
    else:
        stock = stocks.Stock(
            debug=False,
            session=session,
            proxy=proxy,
        )



    tickers_list = {}
    tickers_list['xnas'] = stock.get_xnas_tickers()
    tickers_list['xnys'] = stock.get_xnys_tickers()
    tickers_list['xase'] = stock.get_xase_tickers()

    sp500_tickers = stock.get_sp500_tickers()

    # Test method in class Stock
    stage = 'As Originally Reported'
    stock.get_income_statement('aapl', 'xnas', stage=stage)
    stock.get_balance_sheet_statement('aapl', 'xnas', stage=stage)
    stock.get_cash_flow_statement('aapl', 'xnas', stage=stage)

    stock.get_growth('aapl', 'xnas')
    stock.get_operating_and_efficiency('aapl', 'xnas')
    stock.get_financial_health('aapl', 'xnas')
    stock.get_cash_flow('aapl', 'xnas')


    db = sqlite3.connect(session)

    for exchange in ['nasdaq', 'nyse', 'amex']:
        query = f"SELECT * FROM us_exchange_{exchange}_tickers"
        df = pd.read_sql_query(query, db)
        assert df is not None, f"{query} is not found in database"

    assert 'AAPL' in sp500_tickers

    stage = 'As Originally Reported'.replace(' ', '_').lower()
    for statement in ['income_statement', 'balance_sheet', 'cash_flow']:
        query = f"SELECT * FROM aapl_xnas_{statement}_annual_{stage}"
        df = pd.read_sql_query(query, db)
        assert df is not None, f"{query} is not found in database"

    for statistics in ['growth', 'operating_and_efficiency', 'financial_health','cash_flow']:
        query = f"SELECT * FROM aapl_xnas_{statistics}"
        df = pd.read_sql_query(query, db)
        assert df is not None, f"{query} is not found in database"
