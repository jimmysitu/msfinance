
import os
import time
import sys

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# For Chrome driver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# Form Firefox driver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
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

class StockBase:
    def __init__(self, debug=False, browser='firefox'):
        self.debug = debug
        if('chrome' == browser):
            pass
        else:
            # Default: firefox
            self.options = FirefoxOptions()
            self.download_dir = '/tmp/downloads/' + str(os.getpid())
            self.options.set_preference("browser.download.folderList", 2)
            self.options.set_preference("browser.download.dir", self.download_dir)
            self.options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")

            self.driver = webdriver.Firefox(
                service=FirefoxService(GeckoDriverManager().install()),
                options=self.options
            )

    def __del__(self):
        if not self.debug:
            self.driver.close()

    def get_income_statment(self, stock_symbol, market_name, period='Annual', type='Restated'):
        url = f"https://www.morningstar.com/stocks/{market_name}/{stock_symbol}/financials"
        self.driver.get(url)

        # Select income statement
        income_button = self.driver.find_element(By.ID, "incomeStatement")
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

        if 'Restated' == type:
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
        tmp_file = self.download_dir + f"/Income Statement_{period}_{type}.xls"
        while not os.path.exists(tmp_file):
            time.sleep(1)

        os.rename(tmp_file, self.download_dir + f"/{market_name}_{stock_symbol}_income_statement_{period}_{type}.xls")

# End of class StockBase

