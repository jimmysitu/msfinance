#!/usr/bin/python3

import os
import time
import sys
import stocks

stock = stocks.StockBase(debug=True)
stock.get_income_statement('aapl', 'xnas')
stock.get_balance_sheet_statement('aapl', 'xnas')
stock.get_cash_flow_statement('aapl', 'xnas')

stock.get_growth('aapl', 'xnas')
stock.get_operating_and_efficiency('aapl', 'xnas')
stock.get_financial_health('aapl', 'xnas')
stock.get_cash_flow('aapl', 'xnas')