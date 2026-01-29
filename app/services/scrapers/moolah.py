import random
import time
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings


class MoolahScraper:
    """
    Moolah is a full Selenium-based scraper that requires UI automation
    for all operations due to captcha and session requirements.
    """
    BASE_URL = "https://moolah.vip:8781"
    CHECK_URL = "https://milkywayapp.xyz:8033/ws/service.ashx"
    LOGIN_ENDPOINT = "/default.aspx"
    DASHBOARD_ENDPOINT = "/Store.aspx"
    GAME_NAME = "moolah"
    GAME_INITIAL = "mh"

    LOCATORS = {
        'username': (By.ID, "txtLoginName"),
        'password': (By.ID, "txtLoginPass"),
        'captcha_input': (By.ID, "txtVerifyCode"),
        'captcha_img': (By.ID, "ImageCheck"),
        'login_btn': (By.ID, "btnLogin"),
        'search_input': (By.ID, 'txtSearch'),
        'search_btn': (By.LINK_TEXT, 'Search'),
        'main_iframe': (By.ID, "frm_main_content"),
        'alert_ok': (By.XPATH, "//div[@id='customAlert']/div[2]/button"),
        'mb_ok': (By.ID, 'mb_btn_ok'),
        'mb_msg': (By.XPATH, "//div[@id='mb_msg']/p/font"),
        'close_btn': (By.ID, "Close"),
        'agent_bln': (By.CSS_SELECTOR, "#UserBalance"),
        'add_gold': (By.ID, 'txtAddGold'),
        'note': (By.XPATH, "//textarea[@id='txtReason']"),
        'submit_btn': (By.ID, 'Button1'),
        'create_player_link': (By.LINK_TEXT, 'Create Player'),
        'signup_acc': (By.ID, 'txtAccount'),
        'signup_nick': (By.ID, 'txtNickName'),
        'signup_pass': (By.ID, 'txtLogonPass'),
        'signup_pass2': (By.ID, 'txtLogonPass2'),
    }

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.MOOLAH_USER
        self.password = password or settings.MOOLAH_PASS
        self.driver = None
        self.wait = None
        self.account_position = 2

    def _initialize_driver(self):
        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-gpu")
        self.driver = uc.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def _close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _check_site_status(self) -> bool:
        try:
            response = requests.get(self.CHECK_URL, timeout=10)
            return response.status_code == 200
        except:
            return False

    def _switch_to_default_frame(self):
        self.driver.switch_to.default_content()

    def _switch_to_main_frame(self):
        WebDriverWait(self.driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it(self.LOCATORS['main_iframe'])
        )

    def _get_element(self, locator_key, timeout=3):
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable(self.LOCATORS[locator_key])
        )

    def _wait_visible(self, locator_key, timeout=3):
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located(self.LOCATORS[locator_key])
        )

    def _login(self):
        """Perform login - Note: Moolah requires captcha solving which is complex"""
        self.driver.get(f"{self.BASE_URL}{self.LOGIN_ENDPOINT}")

        try:
            self._switch_to_default_frame()
            el = self._wait_visible('username')
            el.clear()
            el.send_keys(self.username)

            el = self._wait_visible('password')
            el.clear()
            el.send_keys(self.password)

            # Note: Captcha solving would be needed here
            # For now, this is a placeholder
            return False, "Captcha solving not implemented in this scraper"

        except Exception as e:
            return False, str(e)

    async def get_agent_balance(self):
        """
        Note: Moolah requires full Selenium automation with captcha solving.
        This is a placeholder that returns an error indicating the complexity.
        """
        try:
            if not self._check_site_status():
                return None, "Site unreachable"

            self._initialize_driver()
            success, message = self._login()
            
            if not success:
                self._close_driver()
                return None, f"Login failed: {message}"

            # After login, get balance from UI
            try:
                self._switch_to_default_frame()
                result = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located(self.LOCATORS['agent_bln'])
                ).text
                result = result.split(':')[-1].strip()
                self._close_driver()
                return float(result), "Success"
            except Exception as e:
                self._close_driver()
                return None, str(e)

        except Exception as e:
            self._close_driver()
            return None, str(e)

    def _generate_username(self, fullname: str) -> str:
        n = fullname.lower().split()
        base = f"{self.GAME_INITIAL}{n[0]}{n[-1][0]}" if n else f"{self.GAME_INITIAL}user"
        base = base[:10]
        username = f"{base}{random.randrange(100):02d}"
        if len(username) < 7:
            username += "".join(str(random.randint(0, 9)) for _ in range(7 - len(username)))
        return username

    def player_signup(self, fullname: str, requested_username: str = None):
        """
        Note: Moolah requires full Selenium automation with captcha solving.
        This is a placeholder implementation.
        """
        return {
            "status": "error",
            "message": "Moolah requires captcha solving which is not implemented in this scraper. Please use the original worker."
        }

    def recharge_user(self, username: str, amount: float):
        """
        Note: Moolah requires full Selenium automation.
        This is a placeholder implementation.
        """
        return {
            "status": "error",
            "message": "Moolah requires full Selenium automation with captcha solving. Please use the original worker."
        }

    def redeem_user(self, username: str, amount: float):
        """
        Note: Moolah requires full Selenium automation.
        This is a placeholder implementation.
        """
        return {
            "status": "error",
            "message": "Moolah requires full Selenium automation with captcha solving. Please use the original worker."
        }
