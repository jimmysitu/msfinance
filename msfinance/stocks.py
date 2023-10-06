
import os
import shutil
import re
import time
import json
import sqlite3
import requests
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.proxy import Proxy, ProxyType
# For Chrome driver
from webdriver_manager.chrome import ChromeDriverManager

# Form Firefox driver
from webdriver_manager.firefox import GeckoDriverManager

# Mapping statistics string to statistics file name
statistics_filename = {
    'Growth':                       'growthTable',
    'Operating and Efficiency':     'operatingAndEfficiency',
    'Financial Health':             'financialHealth',
    'Cash Flow':                    'cashFlow',
}

class StockBase:
    def __init__(self, debug=False, browser='firefox', session='/tmp/msfinance/msfinance.db', proxy=None):
        self.debug = debug
        if('chrome' == browser):
            pass
        else:
            # Default: firefox
            self.options = webdriver.FirefoxOptions()

            # Settting download staff
            self.download_dir = '/tmp/msfinance/' + str(os.getpid())
            self.options.set_preference("browser.download.folderList", 2)
            self.options.set_preference("browser.download.dir", self.download_dir)
            self.options.set_preference("browser.download.useDownloadDir", True)
            self.options.set_preference("browser.download.viewableInternally.enabledTypes", "")
            self.options.set_preference("browser.download.manager.showWhenStarting", False)
            self.options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")
            # Enable cache
            self.options.set_preference("browser.cache.disk.enable", True);
            self.options.set_preference("browser.cache.memory.enable", True);
            self.options.set_preference("browser.cache.offline.enable", True);
            self.options.set_preference("network.http.use-cache", True);
            # Use headless mode
            if not debug:
                self.options.add_argument("-headless")

            self.webproxy = None
            if proxy:
                [protocal, host, port] = re.split(r'://|:', proxy)
                # Use set_preference method can enable the DNS proxy
                self.options.set_preference('network.proxy.type', 1)
                if 'socks5' == protocal:
                    self.options.set_preference('network.proxy.socks', host)
                    self.options.set_preference('network.proxy.socks_port', int(port))
                    self.options.set_preference('network.proxy.socks_version', 5)
                    self.options.set_preference('network.proxy.socks_remote_dns', True)
                else:
                    print("No supported proxy protocal")
                    exit(1)

#                # May works for Chrome                                     
#                self.options.proxy = Proxy({
#                   'proxyType': ProxyType.MANUAL,
#                   'socksProxy': '127.0.0.1:1088',
#                   'socksVersion': 5,
#                })
#                # Or
#                self.options.add_argument(f"--proxy-server={proxy}")


            self.driver = webdriver.Firefox(
                service=webdriver.FirefoxService(GeckoDriverManager().install()),
                options=self.options,
            )

        # Initial session storage
        if session:
            dir = os.path.dirname(session)
            if dir:
                os.makedirs(dir, exist_ok=True)
            self.db = sqlite3.connect(session)
        else:
            self.db = None 

        # Setup proxies of requests
        self.proxies = {
            "http": proxy,
            "https": proxy,
        }

    def __del__(self):
        if not self.debug:
            self.driver.close()

        # Close database
        if self.db:
            self.db.close()

    def _check_database(self, unique_id):
        '''
        Check database if table with unique_id exists, and return it as a DataFrame

        Args:
            unique_id: Name of the query table

        Returns:
            DataFrame of the table, or None
        '''
        if self.db:
            try:
                query = f"SELECT * FROM {unique_id}"
                df = pd.read_sql_query(query, self.db)
                return df
            except pd.errors.DatabaseError as e:
                return None
        else:
            return None

    def _get_valuation(self, ticker, exchange, statistics, update=False):

        # Compose an unique ID for database table and file name
        unique_id = f"{ticker}_{exchange}_{statistics}".replace(' ', '_').lower()

        # Not force to update, check database first 
        if not update:
            df = self._check_database(unique_id)
            if df is not None:
                return df
        
        # Fetch data from website starts here
        url = f"https://www.morningstar.com/stocks/{exchange}/{ticker}/valuation"
        self.driver.get(url)

        statistics_button = self.driver.find_element(By.XPATH, f"//button[contains(., '{statistics}')]")
        statistics_button.click()
        
        export_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Export Data')]"))
        )
        export_button.click()
        

        # Wait download is done
        tmp_string = statistics_filename[statistics]
        tmp_file = self.download_dir + f"/{tmp_string}.xls"
        while (not os.path.exists(tmp_file) or os.path.getsize(tmp_file) == 0):
            time.sleep(1)

        statistics_file = self.download_dir + f"/{unique_id}.xls"
        os.rename(tmp_file, statistics_file)

        if self.db:
            df = pd.read_excel(statistics_file)
            df.to_sql(unique_id, self.db, if_exists='replace', index=False)

        return df

    def _get_financials(self, ticker, exchange, statement, period='Annual', stage='Restated', update=False):
        
        # Compose an unique ID for database table and file name
        unique_id = f"{ticker}_{exchange}_{statement}_{period}_{stage}".replace(' ', '_').lower()
        
        # Not force to update, check database first 
        if not update:
            df = self._check_database(unique_id)
            if df is not None:
                return df

        # Fetch data from website starts here
        url = f"https://www.morningstar.com/stocks/{exchange}/{ticker}/financials"
        self.driver.get(url)

        # Select income statement
        income_button = self.driver.find_element(By.XPATH, f"//button[contains(., '{statement}')]")
        income_button.click()

        # Select statement period
        period_list_button = self.driver.find_element(By.XPATH, "//button[contains(., 'Annual') and @aria-haspopup='true']")
        period_list_button.click()

        if 'Annual' == period:
            period_button = self.driver.find_element(By.XPATH, "//span[contains(., 'Annual') and @class='mds-list-group__item-text__sal']")
        else:
            period_button = self.driver.find_element(By.XPATH, "//span[contains(., 'Quarterly') and @class='mds-list-group__item-text__sal']")

        period_button.click()

        # Select statement type
        type_list_button = self.driver.find_element(By.XPATH, "//button[contains(., 'As Originally Reported') and @aria-haspopup='true']")
        type_list_button.click()

        if 'Restated' == stage:
            type_button = self.driver.find_element(By.XPATH, "//span[contains(., 'Restated') and @class='mds-list-group__item-text__sal']")
        else:
            type_button = self.driver.find_element(By.XPATH, "//span[contains(., 'As Originally Reported') and @class='mds-list-group__item-text__sal']")

        type_button.click()

        # Expand the detail page
        expand_detail_view = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Expand Detail View')]"))
        )
        expand_detail_view.click()

        export_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Export Data')]"))
        )
        export_button.click()

        # Wait download is done
        tmp_file = self.download_dir + f"/{statement}_{period}_{stage}.xls"
        while not os.path.exists(tmp_file):
            time.sleep(1)

        statement_file = self.download_dir + f"/{unique_id}.xls"
        os.rename(tmp_file, statement_file)
    
        if self.db:
            df = pd.read_excel(statement_file)
            df.to_sql(unique_id, self.db, if_exists='replace', index=False)

        return df

    def _get_us_exchange_tickers(self, exchange, update=False):

        unique_id = f"us_exchange_{exchange}_tickers"

        # Not force to update, check database first 
        if not update:
            df = self._check_database(unique_id)
            if df is not None:
                symbols = df['symbol'].tolist()
                return symbols
        
        # The api.nasdaq.com needs a request with headers, or it won't response
        headers = {
            'accept': 'application/json, text/plain, */*',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.76',
        }
        url=f'https://api.nasdaq.com/api/screener/stocks?tableonly=true&exchange={exchange}&download=true'
        response = requests.get(url, headers=headers)

        tmp_data = json.loads(response.text)
        df = pd.DataFrame(tmp_data['data']['rows'])

        if self.db:
            df.to_sql(unique_id, self.db, if_exists='replace', index=False)

        symbols = df['symbol'].tolist()
        return symbols

# End of class StockBase

class Stock(StockBase):
    '''
    Get stock financials statements and valuations statistics
    '''
    def get_growth(self, ticker, exchange, update=False):
        '''
        Get growth statistics of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
            update: Force update data from website
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Growth'
        return self._get_valuation(ticker, exchange, statistics)
    
    def get_operating_and_efficiency(self, ticker, exchange):
        '''
        Get operating and efficiency statistics of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Operating and Efficiency'
        return self._get_valuation(ticker, exchange, statistics)
    
    def get_financial_health(self, ticker, exchange):
        '''
        Get financial health statistics of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Financial Health'
        return self._get_valuation(ticker, exchange, statistics)
    
    def get_cash_flow(self, ticker, exchange):
        '''
        Get cash flow statistics of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Cash Flow'
        return self._get_valuation(ticker, exchange, statistics)

    def get_valuations(self, ticker, exchange):
        '''
        Get all valuations of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame list of statistics
        '''

        self.valuations = []
        for statistics in ['Growth', 'Operating and Efficiency', 'Financial Health','Cash Flow']:
            df = self._get_valuation(ticker, exchange, statistics)
            self.valuations.append(df)
        
        return self.valuations

    def get_income_statement(self, ticker, exchange, period='Annual', stage='Restated'):
        '''
        Get income statement of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be Annual, Quarterly
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'
        Returns:
            DataFrame of income statement
        '''
        statement = 'Income Statement'
        return self._get_financials(ticker, exchange, statement, period, stage)

    def get_balance_sheet_statement(self, ticker, exchange, period='Annual', stage='Restated'):
        '''
        Get balance sheet statement of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be Annual, Quarterly
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'
        Returns:
            DataFrame of balance sheet statement
        '''
        statement = 'Balance Sheet'
        return self._get_financials(ticker, exchange, statement, period, stage)

    def get_cash_flow_statement(self, ticker, exchange, period='Annual', stage='Restated'):
        '''
        Get cash flow statement of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be Annual, Quarterly
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'
        Returns:
            DataFrame of cash flow statement
        '''
        statement = 'Cash Flow'
        return self._get_financials(ticker, exchange, statement, period, stage)

    def get_financials(self, ticker, exchange, period='Annual', stage='Restated'):
        '''
        Get all financials statements of stock
        
        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be Annual, Quarterly
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'
        Returns:
            DataFrame list of financials statements
        '''

        self.financials = []
        for statement in ['Income Statement', 'Balance Sheet', 'Cash Flow']:
            df = self._get_financials(ticker, exchange, statement, period, stage)
            self.financials.append(df)

        return self.financials

    def get_sp500_tickers(self):
        '''
        Get tickers of sp500

        Returns:
            List of ticker names
        '''
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        response = requests.get(url, proxies=self.proxies)
        tables = pd.read_html(response.text)
        symbols = tables[0]['Symbol'].tolist()
        return symbols
    

    def get_xnas_tickers(self):
        '''
        Get tickers of NASDAQ

        Returns:
            List of ticker names in NASDAQ
        '''
        
        exchange = 'NASDAQ'
        return self._get_us_exchange_tickers(exchange)

    def get_xnys_tickers(self):
        '''
        Get tickers of NYSE

        Returns:
            List of ticker names in NYSE
        '''
        
        exchange = 'NYSE'
        return self._get_us_exchange_tickers(exchange)

    def get_xase_tickers(self):
        '''
        Get tickers of NYSE

        Returns:
            List of ticker names in NYSE
        '''
        
        exchange = 'AMEX'
        return self._get_us_exchange_tickers(exchange)



# End of class Stock