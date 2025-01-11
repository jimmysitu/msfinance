import os
import random
import re
import time
import json
import requests
import tempfile
import logging
import glob

import pandas as pd

from tenacity import retry, wait_random, stop_after_attempt
from datetime import datetime

from selenium import webdriver
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

from fake_useragent import UserAgent

from selenium_stealth import stealth
import undetected_chromedriver as uc

# For Chrome driver
from webdriver_manager.chrome import ChromeDriverManager

# For Firefox driver
from webdriver_manager.firefox import GeckoDriverManager


# Mapping statistics string to statistics file name
statistics_filename = {
    'Financial Summary':            'summary',
    'Growth':                       'growthTable',
    'Profitability and Efficiency': 'profitabilityAndEfficiency',
    'Financial Health':             'financialHealth',
    'Cash Flow':                    'cashFlow',
}


class StockBase:
    def __init__(self, debug=False, browser='chrome', database='msfinance.db3', session_factory=None, proxy=None, driver_type='uc'):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s:%(name)s: %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        # Initialize UserAgent for random user-agent generation
        self.ua = UserAgent()

        self.driver_type = driver_type

        # Setup driver
        if browser == 'chrome':
            if os.environ.get('CHROME_PATH') is not None:
                self.chrome_path = os.environ.get('CHROME_PATH')
            else:
                self.chrome_path = None
            self.setup_chrome_driver(proxy)
        else:
            # Default: firefox
            self.setup_firefox_driver(proxy)

        # Setup session
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
        time.sleep(15)

        self.logger.debug("Driver initialized")

    def __del__(self):
        if not self.debug:
            self.driver.quit()

    def reset_driver(self, retry_state=None):
        '''Reset the driver'''

        if retry_state is not None:
            self.logger.info("Retry State Information:")
            self.logger.info(f"  Attempt number: {retry_state.attempt_number}")
            
            try:
                self.logger.info(f"  Last result: {retry_state.outcome.result()}")
            except Exception as e:
                self.logger.info(f"  Last result: {e}")
            
            try:
                self.logger.info(f"  Last exception: {retry_state.outcome.exception()}")
            except Exception as e:
                self.logger.info(f"  Last exception: {e}")
            
            self.logger.info(f"  Time elapsed: {retry_state.seconds_since_start}")
        

        # Setup a new driver instance
        if isinstance(self.driver, (webdriver.Chrome, uc.Chrome)):
            self.driver.quit()
            self.setup_chrome_driver(self.proxies['http'])
        else:
            self.driver.quit()
            self.setup_firefox_driver(self.proxies['http'])


    def setup_chrome_driver(self, proxy):
        # Chrome support
        self.options = webdriver.ChromeOptions()

        # Set a random user-agent
        self.options.add_argument(f"--user-agent={self.ua.random}")

        # Setting download directory
        self.download_dir = os.path.join(tempfile.gettempdir(), 'msfinance', str(os.getpid()))
        self.logger.debug(f"Download directory: {self.download_dir}")

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        # Use headless mode
        if not self.debug:
            self.options.add_argument("--headless")
        else:
            self.options.add_argument("--start-maximized")
            self.options.add_argument("--disable-popup-blocking")

        if proxy is not None:
            [protocol, host, port] = re.split(r'://|:', proxy)
            if 'socks5' == protocol:
                self.options.add_argument(f'--proxy-server=socks5://{host}:{port}')
            else:
                self.logger.error("No supported proxy protocol")
                exit(1)

        # Initialize the undetected_chromedriver
        self.initialize_chrome_driver()

        # Override the webdriver property, make more undetected 
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        # Change download directory
        params = {
            "behavior": "allow",
            "downloadPath": self.download_dir,
        }
        self.driver.execute_cdp_cmd("Page.setDownloadBehavior", params)

    def setup_firefox_driver(self, proxy):
        self.options = webdriver.FirefoxOptions()

        # Setting download directory
        self.download_dir = os.path.join(tempfile.gettempdir(), 'msfinance', str(os.getpid()))
        self.logger.debug(f"Download directory: {self.download_dir}")

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
        if not self.debug:
            self.options.add_argument("--headless")

        if proxy is not None:
            [protocol, host, port] = re.split(r'://|:', proxy)
            # Use set_preference method to enable the DNS proxy
            self.options.set_preference('network.proxy.type', 1)
            if 'socks5' == protocol:
                self.options.set_preference('network.proxy.socks', host)
                self.options.set_preference('network.proxy.socks_port', int(port))
                self.options.set_preference('network.proxy.socks_version', 5)
                self.options.set_preference('network.proxy.socks_remote_dns', True)
            else:
                self.logger.error("No supported proxy protocol")
                exit(1)

        self.driver = webdriver.Firefox(
            service=webdriver.FirefoxService(GeckoDriverManager().install()),
            options=self.options)

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
            self.logger.info(f"OperationalError: {e}")
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
        actions = ActionChains(self.driver)
        
        element = self.driver.find_element(By.TAG_NAME, 'body')
        target_x = random.randint(100, 200)
        target_y = random.randint(100, 200)
        if self.debug:
            self.logger.debug(f"Simulate random mouse movement, target position: {target_x}, {target_y}")
        actions.move_to_element_with_offset(element, target_x, target_y).perform()
        self._human_delay(1, 5)
        
    def _random_scroll(self):
        '''Simulate random page scrolling'''
        
        scroll_height = self.driver.execute_script("return document.body.scrollHeight")
        random_position = random.randint(scroll_height>>1, scroll_height)
        self.logger.debug(f"Simulate random page scrolling, target position: {random_position}")
        self.driver.execute_script(f"window.scrollTo(0, {random_position});")
        self._human_delay(1, 5)

    def _random_typing(self, element, text):
        '''Simulate random keyboard typing'''
        self.logger.debug(f"Simulate random keyboard typing: {text}")
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.3))  # Random delay between each character

    def _get_key_metrics(self, ticker, exchange, statistics, update=False):
        
        @retry(
            wait=wait_random(min=60, max=120),
            stop=stop_after_attempt(3),
            before_sleep=self.reset_driver
        )
        def _get_key_metrics_retry():
            # Compose a unique ID for database table and file name
            unique_id = f"{ticker}_{exchange}_{statistics}".replace(' ', '_').lower()

            # Not force to update, check database first
            if not update:
                df = self._check_database(unique_id)
                if df is not None:
                    return df

            # Fetch data from website starts here
            url = f"https://www.morningstar.com/stocks/{exchange}/{ticker}/key-metrics"
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
            self._human_delay()
            self._random_scroll()
    
            export_button = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="salKeyStatsPopoverExport"]'))
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

            # Use wildcard to match the file name
            pattern = os.path.join(self.download_dir, f"{tmp_string}*.xls")
    
            retries = 10
            downloaded_files = glob.glob(pattern)
            while retries and (not downloaded_files or os.path.getsize(downloaded_files[0]) == 0):
                time.sleep(1)
                retries -= 1
                downloaded_files = glob.glob(pattern)
    
            if not downloaded_files:
                raise ValueError("Export data fail")
    
            tmp_file = downloaded_files[0]
            statistics_file = self.download_dir + f"/{unique_id}.xls"
            os.rename(tmp_file, statistics_file)
            time.sleep(1)
    
            # Update database
            df = pd.read_excel(statistics_file)
            self._update_database(unique_id, df)
    
            return df

        return _get_key_metrics_retry()
    
    def _get_financials(self, ticker, exchange, statement, period='Annual', stage='Restated', update=False):

        @retry(
            wait=wait_random(min=60, max=120),
            stop=stop_after_attempt(3),
            before_sleep=self.reset_driver
        )
        def _get_financials_retry():
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
            self._random_scroll()
            self._human_delay()
            self._random_mouse_move()
    
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
                    EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Annual') and @class='mds-list-group-item__text__sal']"))
                )
            else:
                period_button = WebDriverWait(self.driver, 30).until(
                    EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Quarterly') and @class='mds-list-group-item__text__sal']"))
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
                    EC.visibility_of_element_located(
                        (By.XPATH, "//span[contains(., 'As Originally Reported') and @class='mds-list-group-item__text__sal']"))
                )
            else:
                stage_button = WebDriverWait(self.driver, 30).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, "//span[contains(., 'Restated') and @class='mds-list-group-item__text__sal']"))
                )
    
            try:
                stage_button.click()
                self._human_delay()
            except ElementClickInterceptedException:
                pass
            except ElementNotInteractableException:
                pass
    
            # More human-like operations
            self._random_mouse_move()
            self._human_delay()
            self._random_scroll()

            export_button = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="salEqsvFinancialsPopoverExport"]'))
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
        
        return _get_financials_retry()
    
    
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

    def initialize_chrome_driver(self):
        # Initialize the driver based on the driver_type
        if self.driver_type == 'uc':
            self.driver = uc.Chrome(
                options=self.options,
                browser_executable_path=self.chrome_path,
                version_main=126,
                use_subprocess=True,
                user_multi_procs=True,
                service=webdriver.ChromeService(ChromeDriverManager(driver_version='126').install()),
                debug=self.debug,
            )
        elif self.driver_type == 'stealth':
            # Initialize the WebDriver (e.g., Chrome)
            self.driver = webdriver.Chrome(
                service=webdriver.ChromeService(ChromeDriverManager(driver_version='126').install()),
                options=self.options,
            )
            
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
    Get stock financials statements and key metrics statistics
    '''
    def get_financial_summary(self, ticker, exchange, update=False):
        '''
        Get financial summary statistics of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
            update: Force update data from website
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Financial Summary'
        return self._get_key_metrics(ticker, exchange, statistics, update)

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
        return self._get_key_metrics(ticker, exchange, statistics, update)

    def get_profitability_and_efficiency(self, ticker, exchange, update=False):
        '''
        Get profitability and efficiency statistics of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame of statistics
        '''
        statistics = 'Profitability and Efficiency'
        return self._get_key_metrics(ticker, exchange, statistics, update)

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
        return self._get_key_metrics(ticker, exchange, statistics, update)

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
        return self._get_key_metrics(ticker, exchange, statistics, update)

    def get_key_metrics(self, ticker, exchange, update=False):
        '''
        Get all key metrics of stock

        Args:
            ticker: Stock symbol
            exchange: Exchange name
        Returns:
            DataFrame list of statistics
        '''

        self.key_metrics = []
        for statistics in ['Financial Summary', 'Growth', 'Profitability and Efficiency', 'Financial Health','Cash Flow']:
            df = self._get_key_metrics(ticker, exchange, statistics, update)
            self.key_metrics.append(df)

        return self.key_metrics

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






















