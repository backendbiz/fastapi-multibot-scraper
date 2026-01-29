"""
Selenium Web Scraping Service.
Provides browser automation for scraping dynamic websites.
"""
import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# Thread pool for running Selenium in async context
_executor = ThreadPoolExecutor(max_workers=4)


class SeleniumScraper:
    """
    Selenium-based web scraper with async support.
    Designed for scraping dynamic JavaScript-rendered pages.
    """

    def __init__(
        self,
        headless: bool = None,
        timeout: int = None,
        user_agent: str = None,
    ):
        """
        Initialize the scraper.

        Args:
            headless: Run in headless mode
            timeout: Default timeout for operations
            user_agent: Custom user agent string
        """
        self.headless = headless if headless is not None else settings.SELENIUM_HEADLESS
        self.timeout = timeout or settings.SELENIUM_TIMEOUT
        self.user_agent = user_agent or settings.SELENIUM_USER_AGENT
        self.page_load_timeout = settings.SELENIUM_PAGE_LOAD_TIMEOUT
        self.implicit_wait = settings.SELENIUM_IMPLICIT_WAIT
        self.screenshots_dir = Path(settings.SCREENSHOTS_DIR)

        # Ensure screenshots directory exists
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def _create_driver(self) -> WebDriver:
        """Create and configure a Chrome WebDriver instance."""
        chrome_options = ChromeOptions()

        # Headless mode
        if self.headless:
            chrome_options.add_argument("--headless=new")

        # Essential options for Docker/containerized environments
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")

        # Window size
        chrome_options.add_argument("--window-size=1920,1080")

        # User agent
        chrome_options.add_argument(f"--user-agent={self.user_agent}")

        # Additional stability options
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")

        # Memory optimization
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")

        # Experimental options
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Set binary location if specified
        if settings.CHROME_BINARY_PATH:
            chrome_options.binary_location = settings.CHROME_BINARY_PATH
        elif os.path.exists("/usr/bin/chromium"):
            chrome_options.binary_location = "/usr/bin/chromium"

        # Create service
        service = None
        if settings.CHROMEDRIVER_PATH:
            service = ChromeService(executable_path=settings.CHROMEDRIVER_PATH)
        elif os.path.exists("/usr/bin/chromedriver"):
            service = ChromeService(executable_path="/usr/bin/chromedriver")

        # Create driver
        try:
            if service:
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {e}")
            raise

        # Configure timeouts
        driver.set_page_load_timeout(self.page_load_timeout)
        driver.implicitly_wait(self.implicit_wait)

        return driver

    @asynccontextmanager
    async def get_driver(self):
        """Async context manager for WebDriver."""
        driver = None
        try:
            driver = await asyncio.get_event_loop().run_in_executor(
                _executor, self._create_driver
            )
            yield driver
        finally:
            if driver:
                await asyncio.get_event_loop().run_in_executor(
                    _executor, driver.quit
                )

    def _scrape_sync(
        self,
        url: str,
        wait_for: Optional[str] = None,
        wait_type: str = "presence",
        extract_rules: Optional[Dict[str, Dict]] = None,
        take_screenshot: bool = False,
        scroll_to_bottom: bool = False,
        wait_time: int = None,
        custom_js: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous scraping method.

        Args:
            url: URL to scrape
            wait_for: CSS selector to wait for
            wait_type: Type of wait (presence, visibility, clickable)
            extract_rules: Rules for data extraction
            take_screenshot: Capture screenshot
            scroll_to_bottom: Scroll to bottom of page
            wait_time: Additional wait time after page load
            custom_js: Custom JavaScript to execute

        Returns:
            Dictionary with scraped data
        """
        driver = self._create_driver()
        result = {
            "url": url,
            "success": False,
            "timestamp": datetime.utcnow().isoformat(),
            "title": None,
            "html": None,
            "data": {},
            "screenshot": None,
            "error": None,
        }

        try:
            # Navigate to URL
            logger.info(f"Navigating to: {url}")
            driver.get(url)

            # Wait for specific element if specified
            if wait_for:
                wait = WebDriverWait(driver, self.timeout)
                wait_conditions = {
                    "presence": EC.presence_of_element_located,
                    "visibility": EC.visibility_of_element_located,
                    "clickable": EC.element_to_be_clickable,
                }
                condition = wait_conditions.get(wait_type, EC.presence_of_element_located)
                wait.until(condition((By.CSS_SELECTOR, wait_for)))

            # Additional wait time
            if wait_time:
                import time
                time.sleep(wait_time)

            # Scroll to bottom if requested
            if scroll_to_bottom:
                self._scroll_to_bottom(driver)

            # Execute custom JavaScript
            if custom_js:
                driver.execute_script(custom_js)

            # Get page info
            result["title"] = driver.title
            result["html"] = driver.page_source

            # Extract data based on rules
            if extract_rules:
                result["data"] = self._extract_data(driver, extract_rules)

            # Take screenshot
            if take_screenshot:
                screenshot_path = self.screenshots_dir / f"screenshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                driver.save_screenshot(str(screenshot_path))
                with open(screenshot_path, "rb") as f:
                    result["screenshot"] = f.read()
                result["screenshot_path"] = str(screenshot_path)

            result["success"] = True
            logger.info(f"Successfully scraped: {url}")

        except TimeoutException as e:
            result["error"] = f"Timeout waiting for page element: {str(e)}"
            logger.error(result["error"])

        except WebDriverException as e:
            result["error"] = f"WebDriver error: {str(e)}"
            logger.error(result["error"])

        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            logger.exception(result["error"])

        finally:
            driver.quit()

        return result

    def _scroll_to_bottom(self, driver: WebDriver, pause_time: float = 0.5):
        """Scroll to the bottom of the page to load lazy content."""
        import time

        last_height = driver.execute_script("return document.body.scrollHeight")

        while True:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause_time)

            # Check new height
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def _extract_data(
        self,
        driver: WebDriver,
        rules: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """
        Extract data from page based on rules.

        Rules format:
        {
            "field_name": {
                "selector": "css selector",
                "attribute": "text" | "href" | "src" | etc.,
                "multiple": True/False,
                "transform": optional callable
            }
        }
        """
        extracted = {}

        for field_name, rule in rules.items():
            try:
                selector = rule.get("selector")
                attribute = rule.get("attribute", "text")
                multiple = rule.get("multiple", False)
                transform = rule.get("transform")

                if multiple:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    values = []
                    for el in elements:
                        value = self._get_element_value(el, attribute)
                        if transform and callable(transform):
                            value = transform(value)
                        values.append(value)
                    extracted[field_name] = values
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    value = self._get_element_value(element, attribute)
                    if transform and callable(transform):
                        value = transform(value)
                    extracted[field_name] = value

            except NoSuchElementException:
                extracted[field_name] = None
                logger.warning(f"Element not found for field: {field_name}")

            except Exception as e:
                extracted[field_name] = None
                logger.error(f"Error extracting {field_name}: {e}")

        return extracted

    def _get_element_value(self, element, attribute: str) -> str:
        """Get value from element based on attribute type."""
        if attribute == "text":
            return element.text.strip()
        elif attribute == "html":
            return element.get_attribute("innerHTML")
        elif attribute == "outer_html":
            return element.get_attribute("outerHTML")
        else:
            return element.get_attribute(attribute)

    async def scrape(
        self,
        url: str,
        wait_for: Optional[str] = None,
        wait_type: str = "presence",
        extract_rules: Optional[Dict[str, Dict]] = None,
        take_screenshot: bool = False,
        scroll_to_bottom: bool = False,
        wait_time: int = None,
        custom_js: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Async method to scrape a URL.

        Args:
            url: URL to scrape
            wait_for: CSS selector to wait for
            wait_type: Type of wait condition
            extract_rules: Data extraction rules
            take_screenshot: Capture screenshot
            scroll_to_bottom: Scroll to load lazy content
            wait_time: Additional wait time
            custom_js: Custom JavaScript to execute

        Returns:
            Dictionary with scraped data
        """
        return await asyncio.get_event_loop().run_in_executor(
            _executor,
            lambda: self._scrape_sync(
                url=url,
                wait_for=wait_for,
                wait_type=wait_type,
                extract_rules=extract_rules,
                take_screenshot=take_screenshot,
                scroll_to_bottom=scroll_to_bottom,
                wait_time=wait_time,
                custom_js=custom_js,
            ),
        )

    async def scrape_multiple(
        self,
        urls: List[str],
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently.

        Args:
            urls: List of URLs to scrape
            **kwargs: Arguments passed to scrape()

        Returns:
            List of scraping results
        """
        tasks = [self.scrape(url, **kwargs) for url in urls]
        return await asyncio.gather(*tasks)

    async def get_page_html(self, url: str, wait_for: Optional[str] = None) -> str:
        """Simple method to get page HTML."""
        result = await self.scrape(url, wait_for=wait_for)
        return result.get("html", "")

    async def get_page_text(self, url: str) -> str:
        """Get all text content from a page."""
        html = await self.get_page_html(url)
        if html:
            soup = BeautifulSoup(html, "lxml")
            return soup.get_text(separator="\n", strip=True)
        return ""


# Global scraper instance
selenium_scraper = SeleniumScraper()
