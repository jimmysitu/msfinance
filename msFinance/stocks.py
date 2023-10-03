
import os
import time
import sys

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# For Chrome driver
from webdriver_manager.chrome import ChromeDriverManager

# Form Firefox driver
from webdriver_manager.firefox import GeckoDriverManager

# Inject JavaScript code to capture events
js_code = """
    document.addEventListener('click', function(event) {
        console.log('Click event:', event);
    });
    document.addEventListener('mouseover', function(event) {
        console.log('Mouseover event:', event);
    });
"""
statistics_filename = {
    'Growth':                       'growthTable',
    'Operating and Efficiency':     'operatingAndEfficiency',
    'Financial Health':             'financialHealth',
    'Cash Flow':                    'cashFlow'
}

class StockBase:
    def __init__(self, debug=False, browser='firefox'):
        self.debug = debug
        if('chrome' == browser):
            pass
        else:
            # Default: firefox
            self.options = webdriver.FirefoxOptions()

            # Settting download staff
            self.download_dir = '/tmp/downloads/' + str(os.getpid())
            self.options.set_preference("browser.download.folderList", 2)
            self.options.set_preference("browser.download.dir", self.download_dir)
            self.options.set_preference("browser.download.useDownloadDir", True)
            self.options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")
            # Enable cache
            self.options.set_preference("browser.cache.disk.enable", True);
            self.options.set_preference("browser.cache.memory.enable", True);
            self.options.set_preference("browser.cache.offline.enable", True);
            self.options.set_preference("network.http.use-cache", True);
            # Use headless mode
            if not debug:
                self.options.add_argument("-headless")

            self.driver = webdriver.Firefox(
                service=webdriver.FirefoxService(GeckoDriverManager().install()),
                options=self.options
            )

    def __del__(self):
        if not self.debug:
            self.driver.close()

    def _get_valuation(self, stock_symbol, market_name, statistics):
        url = f"https://www.morningstar.com/stocks/{market_name}/{stock_symbol}/valuation"
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
        while not os.path.exists(tmp_file):
            time.sleep(1)

        tmp_string = tmp_string.replace(' ', '_').lower()
        statistics_file = self.download_dir + f"/{stock_symbol}_{market_name}_{tmp_string}.xls"
        os.rename(tmp_file, statistics_file)
        return (statistics_file)

    def _get_financials(self, stock_symbol, market_name, statement, period='Annual', stage='Restated'):
        url = f"https://www.morningstar.com/stocks/{market_name}/{stock_symbol}/financials"
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

        tmp_string = f"{statement}_{period}_{stage}".replace(' ', '_').lower()
        statement_file = self.download_dir + f"/{stock_symbol}_{market_name}_{tmp_string}.xls"
        os.rename(tmp_file, statement_file)
        return (statement_file)
    
    # API starts from here
    def get_growth(self, stock_symbol, market_name):
        '''
        Get growth statistics of stock
        
        Args:
            stock_symbol: Stock symbol
            market_name: Market name
        Returns:
            File name with full path of the statistics, in xls format
        '''
        statistics = 'Growth'
        return self._get_valuation(stock_symbol, market_name, statistics)
    
    def get_operating_and_efficiency(self, stock_symbol, market_name):
        '''
        Get operating and efficiency statistics of stock
        
        Args:
            stock_symbol: Stock symbol
            market_name: Market name
        Returns:
            File name with full path of the statistics, in xls format
        '''
        statistics = 'Operating and Efficiency'
        return self._get_valuation(stock_symbol, market_name, statistics)
    
    def get_financial_health(self, stock_symbol, market_name):
        '''
        Get financial health statistics of stock
        
        Args:
            stock_symbol: Stock symbol
            market_name: Market name
        Returns:
            File name with full path of the statistics, in xls format
        '''
        statistics = 'Financial Health'
        return self._get_valuation(stock_symbol, market_name, statistics)
    
    def get_cash_flow(self, stock_symbol, market_name):
        '''
        Get cash flow statistics of stock
        Args:
            stock_symbol: Stock symbol
            market_name: Market name
        Returns:
            File name with full path of the statistics, in xls format
        '''
        statistics = 'Cash Flow'
        return self._get_valuation(stock_symbol, market_name, statistics)
        
    def get_income_statement(self, stock_symbol, market_name, period='Annual', stage='Restated'):
        '''
        Get income statement of stock
        Args:
            stock_symbol: Stock symbol
            market_name: Market name
            period: Period of statement, which can be Annual, Quarterly
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'
        Returns:
            File name with full path of the statement, in xls format
        '''
        statement = 'Income Statement'
        return self._get_financials(stock_symbol, market_name, statement, period, stage)

    def get_balance_sheet_statement(self, stock_symbol, market_name, period='Annual', stage='Restated'):
        '''
        Get balance sheet statement of stock
        Args:
            stock_symbol: Stock symbol
            market_name: Market name
            period: Period of statement, which can be Annual, Quarterly
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'
        Returns:
            File name with full path of the statement, in xls format
        '''
        statement = 'Balance Sheet'
        return self._get_financials(stock_symbol, market_name, statement, period, stage)

    def get_cash_flow_statement(self, stock_symbol, market_name, period='Annual', stage='Restated'):
        '''
        Get cash flow statement of stock
        Args:
            stock_symbol: Stock symbol
            market_name: Market name
            period: Period of statement, which can be Annual, Quarterly
            stage: Stage of statement, which can be 'As Originally Reported', 'Restated'
        Returns:
            File name with full path of the statement, in xls format
        '''
        statement = 'Cash Flow'
        return self._get_financials(stock_symbol, market_name, statement, period, stage)

# End of class StockBase

