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

    async def get_agent_balance(self):
        """
        Fetches agent balance directly via the API service, faster than Selenium.
        """
        import hashlib
        import requests
        
        try:
            # Logic ported from firekirinmilkyorionpanda_balancer.py
            def md5_hash(text):
                return hashlib.md5(text.encode()).hexdigest()

            login_params = {
                "action": "agentLogin",
                "agentName": self.username,
                "agentPasswd": md5_hash(self.password),
                "time": str(int(time.time() * 1000))
            }
            
            # Using synchronous requests here inside async method is okay for now, 
            # ideally use httpx for async
            response = requests.post(self.CHECK_URL, params=login_params, timeout=10)
            data = response.json()
            
            if data.get("code") == '200':
                return float(data.get("balance")), "Success"
            return None, data.get("msg", "Unknown API error")
            
        except Exception as e:
            return None, f"Agent balance fetch failed: {str(e)}"

    def _generate_username(self, fullname: str) -> str:
        import random
        n = fullname.lower().split()
        # simplified logic from original
        base = f"pm{n[0][0]}{n[-1][0]}" if n else "pmuser"
        base = base[:5]
        username = f"{base}{random.randrange(1000):03d}"
        if len(username) < 7:
            username += "".join(str(random.randint(0, 9)) for _ in range(7 - len(username)))
        return username

    def player_signup(self, fullname: str, requested_username: str = None):
        """
        Performs player signup.
        """
        if not self.login():
            return {"status": "error", "message": "Login failed"}
            
        try:
            from app.services.receipts.receipt_generator import save_receipt
            
            # Generate credentials if needed
            import random
            
            if not requested_username:
                requested_username = self._generate_username(fullname)
            
            # Use requested_username as password for simplicity or generate one
            password = requested_username 
            nickname = fullname.replace(" ", "")[:10]

            self._switch_to_main_frame()
            self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Create Player'))).click()
            
            # Switch to nested iframe (logic from original _switch_to_nested_iframe)
            self._switch_to_default_frame()
            # Wait for 4 iframes to be present as per original logic
            self.wait.until(lambda d: len(d.find_elements(By.TAG_NAME, "iframe")) >= 4)
            target_frame = self.driver.find_elements(By.TAG_NAME, "iframe")[3]
            self.driver.switch_to.frame(target_frame)

            # Fill Form
            self.wait.until(EC.element_to_be_clickable((By.ID, 'txtAccount'))).send_keys(requested_username)
            self.driver.find_element(By.ID, 'txtNickName').send_keys(nickname)
            self.driver.find_element(By.ID, 'txtLogonPass').send_keys(password)
            self.driver.find_element(By.ID, 'txtLogonPass2').send_keys(password)
            
            self.driver.find_element(By.LINK_TEXT, 'Create Player').click()

            # Save Receipt
            # Note: save_receipt needs bot instance, which we might not have in this context.
            # For now returning placeholder or skipping receipt generation in this strict port.
            receipt_link = "Receipt generation requires telegram bot instance"
            
            self._switch_to_default_frame()
            
            # Handle Msg Box
            raw_msg = self.wait.until(EC.presence_of_element_located(self.LOCATORS['mb_msg'])).text
            self.driver.find_element(*self.LOCATORS['mb_ok']).click()

            status = "Added successfully" in raw_msg
            
            return {
                "status": "success" if status else "failure",
                "message": raw_msg,
                "username": requested_username,
                "password": password,
                "receipt_link": receipt_link
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def recharge_user(self, username: str, amount: float):
        """
        Recharges a user account.
        """
        return self._perform_transaction(username, amount, "recharge")

    def redeem_user(self, username: str, amount: float):
        """
        Redeems from a user account.
        """
        # Redeem implies negative flow in some contexts, but function takes positive amount usually
        # Original logic used abs(amount) and flow_type.
        return self._perform_transaction(username, amount, "redeem")

    def _perform_transaction(self, username: str, amount: float, flow_type: str):
        if not self.login():
            return {"status": "error", "message": "Login failed"}

        try:
            # 1. Verify User exists and get balance
            user_exists = self._verify_user_in_table(username)
            if not user_exists:
                return {"status": "error", "message": "User not found in table"}

            # 2. Perform Transaction
            self._switch_to_main_frame()
            link_text = 'Recharge' if flow_type == 'recharge' else 'Redeem'
            self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, link_text))).click()
            
            # Switch to nested
            self._switch_to_default_frame()
            self.wait.until(lambda d: len(d.find_elements(By.TAG_NAME, "iframe")) >= 4)
            target_frame = self.driver.find_elements(By.TAG_NAME, "iframe")[3]
            self.driver.switch_to.frame(target_frame)

            # Fill Amount
            add_gold = self.wait.until(EC.element_to_be_clickable(self.LOCATORS['add_gold']))
            add_gold.clear()
            add_gold.send_keys(str(abs(amount)))
            
            self.driver.find_element(*self.LOCATORS['note']).send_keys("bot transaction")
            self.driver.find_element(*self.LOCATORS['submit_btn']).click()
            
            self._switch_to_default_frame()
            raw_msg = self.wait.until(EC.presence_of_element_located(self.LOCATORS['mb_msg'])).text
            self.driver.find_element(*self.LOCATORS['mb_ok']).click()
            
            return {
                "status": "success" if "Confirmed successful" in raw_msg else "failure",
                "message": raw_msg
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _verify_user_in_table(self, target_username: str) -> bool:
        """
        Scans values in the table to find the user.
        """
        target_username = target_username.lower()
        self._switch_to_main_frame()
        
        # Reset search if needed
        try:
            search_field = self.wait.until(EC.element_to_be_clickable(self.LOCATORS['search_input']))
            search_field.clear()
            search_field.send_keys(target_username)
            self.driver.find_element(*self.LOCATORS['search_btn']).click()
            
            # Check first few rows
            for i in range(2, 7): # rows 2 to 6
                try:
                    xpath = f"//table[@id='item']/tbody/tr[{i}]/td[3]"
                    username = self.driver.find_element(By.XPATH, xpath).text.strip().lower()
                    if username == target_username:
                        self._switch_to_default_frame()
                        return True
                except:
                    break
        except Exception:
            pass
            
        self._switch_to_default_frame()
        return False
