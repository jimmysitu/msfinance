import os
import random
import re
import time
import json
import sqlite3
import requests
import tempfile

import pandas as pd

from retrying import retry
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import TimeoutException

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from selenium_stealth import stealth
import undetected_chromedriver as uc

# For Chrome driver
from webdriver_manager.chrome import ChromeDriverManager

# For Firefox driver
from webdriver_manager.firefox import GeckoDriverManager

from fake_useragent import UserAgent

# Mapping statistics string to statistics file name
statistics_filename = {
    'Growth':                       'growthTable',
    'Operating and Efficiency':     'operatingAndEfficiency',
    'Financial Health':             'financialHealth',
    'Cash Flow':                    'cashFlow',
}

class StockBase:
    def __init__(self, debug=False, browser='chrome', database='msfinance.db3', session_factory=None, proxy=None, driver_type='uc'):
        self.debug = debug
        
        # Initialize UserAgent for random user-agent generation
        self.ua = UserAgent()

        self.driver_type = driver_type

        if browser == 'chrome':
            self.setup_chrome_driver(proxy)
        else:
            # Default: firefox
            self.options = webdriver.FirefoxOptions()

            # Setting download directory
            self.download_dir = os.path.join(tempfile.gettempdir(), 'msfinance', str(os.getpid()))
            if debug:
                print(f"Download directory: {self.download_dir}")

            if not os.path.exists(self.download_dir):
                os.makedirs(self.download_dir)

            self.options.set_preference("browser.download.folderList", 2)
            self.options.set_preference("browser.download.dir", self.download_dir)
            self.options.set_preference("browser.download.useDownloadDir", True)
            self.options.set_preference("browser.download.viewableInternally.enabledTypes", "")
            self.options.set_preference("browser.download.manager.showWhenStarting", False)
            self.options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")
            # Enable cache
            self.options.set_preference("browser.cache.disk.enable", True)
            self.options.set_preference("browser.cache.memory.enable", True)
            self.options.set_preference("browser.cache.offline.enable", True)
            self.options.set_preference("network.http.use-cache", True)

            self.options.set_preference("general.useragent.override", self.ua.random)

            # Use headless mode
            if not debug:
                self.options.add_argument("--headless")

            if proxy:
                [protocol, host, port] = re.split(r'://|:', proxy)
                # Use set_preference method to enable the DNS proxy
                self.options.set_preference('network.proxy.type', 1)
                if 'socks5' == protocol:
                    self.options.set_preference('network.proxy.socks', host)
                    self.options.set_preference('network.proxy.socks_port', int(port))
                    self.options.set_preference('network.proxy.socks_version', 5)
                    self.options.set_preference('network.proxy.socks_remote_dns', True)
                else:
                    print("No supported proxy protocol")
                    exit(1)

            self.driver = webdriver.Firefox(
                service=webdriver.FirefoxService(GeckoDriverManager().install()),
                options=self.options)

        if session_factory is not None:
            self.Session = session_factory
        else:
            # Setup SQLAlchemy engine and session
            self.engine = create_engine(f'sqlite:///{database}', pool_size=5, max_overflow=10)
            self.Session = sessionmaker(bind=self.engine)


        # Setup proxies for requests
        self.proxies = {
            "http": proxy,
            "https": proxy,
        }

        # Open Morningstar stock page
        url = f"https://www.morningstar.com/stocks"
        self.driver.get(url)
        time.sleep(20)

    def __del__(self):
        if not self.debug:
            self.driver.quit()

    def setup_chrome_driver(self, proxy):
        # Chrome support
        self.options = webdriver.ChromeOptions()

        # Set a random user-agent
        self.options.add_argument(f"--user-agent={self.ua.random}")

        # Setting download directory
        self.download_dir = os.path.join(tempfile.gettempdir(), 'msfinance', str(os.getpid()))
        if self.debug:
            print(f"Download directory: {self.download_dir}")

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        # Use headless mode
        if not self.debug:
            self.options.add_argument("--headless")
        else:
            self.options.add_argument("--start-maximized")
            self.options.add_argument("--disable-popup-blocking")

        if proxy:
            [protocol, host, port] = re.split(r'://|:', proxy)
            if 'socks5' == protocol:
                self.options.add_argument(f'--proxy-server=socks5://{host}:{port}')
            else:
                print("No supported proxy protocol")
                exit(1)

        # Initialize the undetected_chromedriver
        self.initialize_driver()

        # Change download directory
        params = {
            "behavior": "allow",
            "downloadPath": self.download_dir,
        }
        self.driver.execute_cdp_cmd("Page.setDownloadBehavior", params)

    def _check_database(self, unique_id):
        '''
        Check database if table with unique_id exists, and return it as a DataFrame

        Args:
            unique_id: Name of the query table

        Returns:
            DataFrame of the table, or None
        '''
        session = self.Session()
        try:
            query = f"SELECT * FROM '{unique_id}'"
            df = pd.read_sql_query(query, session.bind)
            return df
        except sqlalchemy.exc.OperationalError as e:
            # Log the error or handle it as needed
            print(f"OperationalError: {e}")
            return None
        finally:
            session.close()

    def _update_database(self, unique_id, df):
        '''
        Update database with unique_id as table name, using DataFrame format data.
        Add 'Last Updated' column to each record

        Args:
            unique_id: Name of the table

        Returns:
            True if update is done, else False
        '''
        session = self.Session()
        try:
            df['Last Updated'] = datetime.now()
            df.to_sql(unique_id, session.bind, if_exists='replace', index=False)
            return True
        finally:
            session.close()

    def _human_delay(self, min=3, max=15):
        '''Simulate human-like random delay'''
        time.sleep(random.uniform(min, max))

    def _random_mouse_move(self):
        '''Simulate random mouse movement'''
        if self.debug:
            print("Simulate random mouse movement")
        actions = ActionChains(self.driver)
        
        element = self.driver.find_element(By.TAG_NAME, 'body')
        target_x = random.randint(100, 200)
        target_y = random.randint(100, 200)
        if self.debug:
            print(f"Target position: {target_x}, {target_y}")
        actions.move_to_element_with_offset(element, target_x, target_y).perform()
        self._human_delay(1, 5)
        
    def _random_scroll(self):
        '''Simulate random page scrolling'''
        if self.debug:
            print("Simulate random page scrolling")
        scroll_height = self.driver.execute_script("return document.body.scrollHeight")
        random_position = random.randint(5, scroll_height>>2 + 1)
        self.driver.execute_script(f"window.scrollTo(0, {random_position});")
        self._human_delay(1, 5)

    def _random_click(self):
        '''Simulate random click on a blank area of the page'''
        if self.debug:
            print("Simulate random click on a blank area of the page")
        window_size = self.driver.get_window_size()
        x = random.randint(0, window_size['width'] - 100)
        y = random.randint(0, window_size['height'] - 100)
        try:
            actions = ActionChains(self.driver)
            actions.move_by_offset(x, y).click().perform()
            self._human_delay(1, 5)
            # Reset mouse position
            actions.move_by_offset(-x, -y).perform()
        except Exception:
            pass  # Ignore exceptions from failed clicks

    def _random_typing(self, element, text):
        '''Simulate random keyboard typing'''
        if self.debug:
            print(f"Simulate random keyboard typing: {text}")
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.3))  # Random delay between each character

    @retry(wait_random_min=1000, wait_random_max=5000, stop_max_attempt_number=3)
    def _get_valuation(self, ticker, exchange, statistics, update=False):

        # Compose a unique ID for database table and file name
        unique_id = f"{ticker}_{exchange}_{statistics}".replace(' ', '_').lower()

        # Not force to update, check database first
        if not update:
            df = self._check_database(unique_id)
            if df is not None:
                return df

        # Fetch data from website starts here
        url = f"https://www.morningstar.com/stocks/{exchange}/{ticker}/valuation"
        self.driver.get(url)

        # Simulate human-like operations
        self._random_mouse_move()
        self._human_delay()
        self._random_scroll()

        statistics_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, f"//button[contains(., '{statistics}')]"))
        )
        statistics_button.click()

        # More human-like operations
        self._random_click()
        self._human_delay()
        self._random_scroll()

        export_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Export Data')]"))
        )

        # Check if there is no such data available
        try:
            WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located(
                    (By.XPATH, f"//div[contains(., 'There is no {statistics} data available.')]")
                )
            )
            return None
        except TimeoutException:
            export_button.click()

        # Wait for download to complete
        tmp_string = statistics_filename[statistics]
        tmp_file = self.download_dir + f"/{tmp_string}.xls"

        retries = 5
        while retries and (not os.path.exists(tmp_file) or os.path.getsize(tmp_file) == 0):
            time.sleep(1)
            retries = retries - 1

        if 0 == retries and (not os.path.exists(tmp_file)):
            raise ValueError("Export data fail")

        statistics_file = self.download_dir + f"/{unique_id}.xls"
        os.rename(tmp_file, statistics_file)
        time.sleep(1)

        # Update database
        df = pd.read_excel(statistics_file)
        self._update_database(unique_id, df)

        return df

    @retry(wait_random_min=1000, wait_random_max=5000, stop_max_attempt_number=3)
    def _get_financials(self, ticker, exchange, statement, period='Annual', stage='Restated', update=False):

        # Compose a unique ID for database table and file name
        unique_id = f"{ticker}_{exchange}_{statement}_{period}_{stage}".replace(' ', '_').lower()

        # Not force to update, check database first
        if not update:
            df = self._check_database(unique_id)
            if df is not None:
                return df

        # Fetch data from website starts here
        url = f"https://www.morningstar.com/stocks/{exchange}/{ticker}/financials"
        self.driver.get(url)

        # Simulate human-like operations
        self._random_mouse_move()
        self._human_delay()
        self._random_scroll()

        # Select statement type
        type_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, f"//button[contains(., '{statement}')]"))
        )
        type_button.click()

        # More human-like operations
        self._random_click()
        self._human_delay()
        self._random_scroll()

        # Select statement period
        period_list_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Annual') and @aria-haspopup='true']"))
        )
        try:
            period_list_button.click()
            self._human_delay()
        except ElementClickInterceptedException:
            pass

        if 'Annual' == period:
            period_button = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Annual') and @class='mds-list-group__item-text__sal']"))
            )
        else:
            period_button = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Quarterly') and @class='mds-list-group__item-text__sal']"))
            )

        try:
            period_button.click()
            self._human_delay()
        except ElementClickInterceptedException:
            pass

        # Select statement stage
        stage_list_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'As Originally Reported') and @aria-haspopup='true']"))
        )
        try:
            stage_list_button.click()
            self._human_delay()
        except ElementClickInterceptedException:
            pass
        except ElementNotInteractableException:
            pass

        if 'As Originally Reported' == stage:
            stage_button = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'As Originally Reported') and @class='mds-list-group__item-text__sal']"))
            )
        else:
            stage_button = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Restated') and @class='mds-list-group__item-text__sal']"))
            )

        try:
            stage_button.click()
            self._human_delay()
        except ElementClickInterceptedException:
            pass
        except ElementNotInteractableException:
            pass

        # Expand the detail page
        expand_detail_view = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Expand Detail View')]"))
        )
        expand_detail_view.click()

        # More human-like operations
        self._random_mouse_move()
        self._human_delay()
        self._random_scroll()

        export_button = WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Export Data')]"))
        )
        export_button.click()

        retries = 5
        # Wait for download to complete
        tmp_file = self.download_dir + f"/{statement}_{period}_{stage}.xls"
        while retries and (not os.path.exists(tmp_file)):
            time.sleep(1)
            retries = retries - 1

        if 0 == retries and (not os.path.exists(tmp_file)):
            raise ValueError("Export data fail")

        statement_file = self.download_dir + f"/{unique_id}.xls"
        os.rename(tmp_file, statement_file)
        time.sleep(1)

        # Update database
        df = pd.read_excel(statement_file)
        self._update_database(unique_id, df)

        return df

    def _get_us_exchange_tickers(self, exchange, update=False):

        unique_id = f"us_exchange_{exchange}_tickers"

        # Not force to update, check database first
        if not update:
            df = self._check_database(unique_id)
            if df is not None:
                symbols = df['symbol'].tolist()
                return symbols

        # Use fake_useragent to generate a random user-agent
        headers = {
            'accept': 'application/json, text/plain, */*',
            'user-agent': self.ua.random,  # Use random user-agent
        }
        url=f'https://api.nasdaq.com/api/screener/stocks?tableonly=true&exchange={exchange}&download=true'
        response = requests.get(url, headers=headers)

        tmp_data = json.loads(response.text)
        df = pd.DataFrame(tmp_data['data']['rows'])

        # Update datebase
        self._update_database(unique_id, df)

        symbols = df['symbol'].tolist()
        return symbols

    def initialize_driver(self):
        # Initialize the driver based on the driver_type
        if self.driver_type == 'uc':
            self.driver = uc.Chrome(
                version_main=126,
                use_subprocess=False,
                service=webdriver.ChromeService(ChromeDriverManager(driver_version='126').install()),
                options=self.options)
        elif self.driver_type == 'stealth':
            # Initialize the WebDriver (e.g., Chrome)
            self.driver = webdriver.Chrome(
                service=webdriver.ChromeService(ChromeDriverManager(driver_version='126').install()),
                options=self.options)
            
            # Apply selenium-stealth to the WebDriver
            stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
        else:
            raise ValueError("Invalid driver type specified")

    def check_for_bot_confirmation(self):
        '''Check if the page contains the string "Let's confirm you aren't a bot"'''
        try:
            # Use XPath to search for the text in the entire page
            self.driver.find_element(By.XPATH, "//*[contains(text(), \"Let's confirm you aren't a bot\")]")
            return True
        except NoSuchElementException:
            return False

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
        return self._get_valuation(ticker, exchange, statistics, update)

    def get_operating_and_efficiency(self, ticker, exchange, update=False):
        '''
        Get operating and efficiency statistics of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Operating and Efficiency'
        return self._get_valuation(ticker, exchange, statistics, update)

    def get_financial_health(self, ticker, exchange, update=False):
        '''
        Get financial health statistics of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Financial Health'
        return self._get_valuation(ticker, exchange, statistics, update)

    def get_cash_flow(self, ticker, exchange, update=False):
        '''
        Get cash flow statistics of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Cash Flow'
        return self._get_valuation(ticker, exchange, statistics, update)

    def get_valuations(self, ticker, exchange, update=False):
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
            df = self._get_valuation(ticker, exchange, statistics, update)
            self.valuations.append(df)

        return self.valuations

    def get_income_statement(self, ticker, exchange, period='Annual', stage='Restated', update=False):
        '''
        Get income statement of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be 'Annual'(default), 'Quarterly'
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'(default)
        Returns:
            DataFrame of income statement
        '''
        statement = 'Income Statement'
        return self._get_financials(ticker, exchange, statement, period, stage, update)

    def get_balance_sheet_statement(self, ticker, exchange, period='Annual', stage='Restated', update=False):
        '''
        Get balance sheet statement of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be 'Annual'(default), 'Quarterly'
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'(default)
        Returns:
            DataFrame of balance sheet statement
        '''
        statement = 'Balance Sheet'
        return self._get_financials(ticker, exchange, statement, period, stage, update)

    def get_cash_flow_statement(self, ticker, exchange, period='Annual', stage='Restated', update=False):
        '''
        Get cash flow statement of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be 'Annual'(default), 'Quarterly'
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'(default)
        Returns:
            DataFrame of cash flow statement
        '''
        statement = 'Cash Flow'
        return self._get_financials(ticker, exchange, statement, period, stage, update)

    def get_financials(self, ticker, exchange, period='Annual', stage='As Originally Reported', update=False):
        '''
        Get all financials statements of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
            period: Period of statement, which can be 'Annual'(default), 'Quarterly'
            stage: Stage of statement, which can be 'As Originally Reported'(default), 'Restated'
        Returns:
            DataFrame list of financials statements
        '''

        self.financials = []
        for statement in ['Income Statement', 'Balance Sheet', 'Cash Flow']:
            df = self._get_financials(ticker, exchange, statement, period, stage, update)
            self.financials.append(df)

        return self.financials

    def get_hsi_tickers(self):
        '''
        Get ticker of Hang Seng Index

        Returns:
            List of ticker with 5-digit number string
        '''
        url = "https://en.wikipedia.org/wiki/Hang_Seng_Index"
        response = requests.get(url, proxies=self.proxies)
        tables = pd.read_html(response.text)
        symbols = tables[6]['Ticker'].tolist()
        pfx_len = len('SEHK:\xa0')
        symbols = [s[pfx_len:].zfill(5) for s in symbols]
        return symbols


    def get_sp500_tickers(self):
        '''
        Get tickers of SP500

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
        exchange = 'nasdaq'
        return self._get_us_exchange_tickers(exchange)

    def get_xnys_tickers(self):
        '''
        Get tickers of NYSE

        Returns:
            List of ticker names in NYSE
        '''
        exchange = 'nyse'
        return self._get_us_exchange_tickers(exchange)

    def get_xase_tickers(self):
        '''
        Get tickers of AMEX

        Returns:
            List of ticker names in AMEX
        '''
        exchange = 'amex'
        return self._get_us_exchange_tickers(exchange)

# End of class Stock







