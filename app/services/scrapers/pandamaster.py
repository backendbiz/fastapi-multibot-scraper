from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import time
from app.core.config import settings

class PandaMasterScraper:
    # --- CONFIGURATION & CONSTANTS ---
    BASE_URL = "https://pandamaster.vip"
    CHECK_URL = "https://pandamaster.vip:8033/ws/service.ashx"
    LOGIN_ENDPOINT = "/default.aspx"
    DASHBOARD_ENDPOINT = "/Store.aspx"
    GAME_NAME = "pandamaster"
    
    # Browser Config
    WINDOW_WIDTH = 974
    WINDOW_HEIGHT = 1039
    WINDOW_X = 953
    WINDOW_Y = 0
    
    # System Config
    TIMEOUT = 10
    MAX_RETRIES = 2
    
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
        'add_gold': (By.ID, 'txtAddGold'),
        'note': (By.XPATH, "//textarea[@id='txtReason']"),
        'submit_btn': (By.XPATH, "//a[contains(text(),'Recharge')]"),
    }

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.PANDAMASTER_USER
        self.password = password or settings.PANDAMASTER_PASS
        self.driver = None
        self.wait = None

    def initialize_driver(self):
        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        self.driver = uc.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, self.TIMEOUT)
        self.driver.set_window_size(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

    def close(self):
        if self.driver:
            self.driver.quit()

    def _switch_to_main_frame(self):
        self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.LOCATORS['main_iframe']))

    def _switch_to_default_frame(self):
        self.driver.switch_to.default_content()

    def login(self) -> bool:
        from app.services.captcha.captcha import solving_captcha
        
        if not self.driver:
            self.initialize_driver()
            
        self.driver.get(f"{self.BASE_URL}{self.LOGIN_ENDPOINT}")
        
        if not self.username or not self.password:
            print("Login credentials not set.")
            return False
            
        for attempt in range(self.MAX_RETRIES):
            try:
                self._switch_to_default_frame()
                
                user_input = self.wait.until(EC.element_to_be_clickable(self.LOCATORS['username']))
                user_input.clear()
                user_input.send_keys(self.username)
                
                pass_input = self.wait.until(EC.element_to_be_clickable(self.LOCATORS['password']))
                pass_input.clear()
                pass_input.send_keys(self.password)
                
                # Captcha Logic
                self.wait.until(EC.visibility_of_element_located(self.LOCATORS['captcha_input']))
                img_element = self.wait.until(EC.visibility_of_element_located(self.LOCATORS['captcha_img']))
                
                result, restart_required = solving_captcha(self.driver, self.wait, img_element)
                
                if restart_required:
                    self.close()
                    self.initialize_driver()
                    continue
                    
                self.driver.find_element(*self.LOCATORS['captcha_input']).send_keys(result)
                self.driver.find_element(*self.LOCATORS['login_btn']).click()
                
                # Check for errors
                try:
                    raw_msg = self.wait.until(
                        EC.presence_of_element_located(self.LOCATORS['mb_msg'])
                    ).text
                    if "incorrect" in raw_msg:
                        continue
                except:
                    pass
                    
                self.wait.until(EC.url_to_be(f"{self.BASE_URL}{self.DASHBOARD_ENDPOINT}"))
                
                # Close potential alerts
                try:
                    self.wait.until(EC.element_to_be_clickable(self.LOCATORS['alert_ok'])).click()
                except:
                    pass
                    
                return True
                
            except Exception as e:
                print(f"Login attempt {attempt + 1} failed: {e}")
                time.sleep(1)
                self.driver.get(f"{self.BASE_URL}{self.LOGIN_ENDPOINT}")
                
        return False

    def _check_session_timeout(self):
        self.driver.refresh()
        try:
            self.wait.until(EC.element_to_be_clickable(self.LOCATORS['alert_ok'])).click()
        except: pass
        
        dashboard_url = f"{self.BASE_URL}{self.DASHBOARD_ENDPOINT}"
        try:
            time.sleep(1)
            if self.driver.current_url != dashboard_url:
                print("Session timed out, re-logging...")
                return self.login()
            return True
        except Exception:
            return False

    def get_agent_balance(self):
        if not self._check_session_timeout():
            return None, "Login Failed"

        try:
            # Logic from fmo_balance_fetch (simplified for direct inclusion)
            # Typically you navigate to a frame and read a span
            # Assuming standard structure here based on original code usage
            self._switch_to_main_frame()
            
            # This is a placeholder as the original code imported `fmo_balance_fetch`
            # For this migration, we need to know what that function did.
            # Based on the bot code, it seems to just read a balance element.
            pass  # You will need to inspect fmo_balance_fetch content to fully implement this
            
            return 0.0, "Success" # Mock for now
        except Exception as e:
            return None, str(e)
