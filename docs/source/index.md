# msfinance documentation.

## Introduction
msfinance offers Pythonic way to download stocks financial data from [morningstar.com/stocks](https://www.morningstar.com/stocks)

## Installation
```bash
pip install msfinance
```

## Quick Start
```python
#!/usr/bin/python3 -u
import msfinance as msf

stock = msf.Stock(
    session='msf_database.db3',
)


print(stock.get_income_statement('aapl', 'xnas'))
print(stock.get_balance_sheet_statement('aapl', 'xnas'))
print(stock.get_cash_flow_statement('aapl', 'xnas'))

print(stock.get_growth('aapl', 'xnas'))
print(stock.get_operating_and_efficiency('aapl', 'xnas'))
print(stock.get_financial_health('aapl', 'xnas'))
print(stock.get_cash_flow('aapl', 'xnas'))
```
- More example is placed in [example](https://github.com/jimmysitu/msfinance/tree/main/example) directory. Add msfinance path to environment variable: PYTHONPATH, and run examples directly 

## [API](api.rst)


```{toctree}
:maxdepth: 2
:hidden:

api
```
