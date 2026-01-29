import json
import time
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings

class VegasXScraper:
    BASE_URL = "https://cashier.vegas-x.org"
    ENDPOINTS = {
        "agent_balance": f"{BASE_URL}/shop/get/logs",
        "user_list": f"{BASE_URL}/shop/get/users",
        "check_player": f"{BASE_URL}/user/check/credits",
        "deposit": f"{BASE_URL}/user/update/credits/in",
        "withdraw": f"{BASE_URL}/user/update/credits/out",
        "pwReset": f"{BASE_URL}/user/update/profile"
    }
    GAME_NAME = "vegas-x"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.VEGASX_USER
        self.password = password or settings.VEGASX_PASS
        self.headers = None
        self.user_cache = {}

    def _fill_input_fields(self, driver):
        user_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.XPATH, "//input[@name='username']"))
        )
        pass_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.XPATH, "//input[@name='password']"))
        )
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Sign in')]"))
        )
        
        user_input.click()
        user_input.clear()
        user_input.send_keys(self.username)
        
        pass_input.click()
        pass_input.clear()
        pass_input.send_keys(self.password)
        
        return login_btn

    def _fetch_token_selenium(self):
        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-gpu")
        
        caps = options.to_capabilities()
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}

        driver = uc.Chrome(options=options)
        
        try:
            driver.get(f"{self.BASE_URL}/login")
            login_btn = self._fill_input_fields(driver)
            login_btn.click()
            
            WebDriverWait(driver, 20).until(EC.url_to_be(f"{self.BASE_URL}/"))
            time.sleep(2)
            driver.refresh()
            WebDriverWait(driver, 20).until(EC.url_to_be(f"{self.BASE_URL}/"))
            time.sleep(3)
            
            logs = driver.get_log("performance")
            
            for entry in logs:
                try:
                    log = json.loads(entry["message"])["message"]
                    if log["method"] == "Network.requestWillBeSentExtraInfo":
                        headers = log["params"]["headers"]
                        if "x-csrf-token" in headers and "cookie" in headers and len(headers["cookie"]) > 150:
                            self.headers = {
                                'accept': '*/*',
                                'accept-language': 'en-US,en;q=0.9',
                                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                'cookie': headers["cookie"],
                                'origin': self.BASE_URL,
                                'referer': self.BASE_URL,
                                'sec-ch-ua': headers.get("sec-ch-ua"),
                                'sec-ch-ua-mobile': '?0',
                                'sec-ch-ua-platform': '"Windows"',
                                'sec-fetch-dest': 'empty',
                                'sec-fetch-mode': 'cors',
                                'sec-fetch-site': 'same-origin',
                                'user-agent': headers.get("user-agent"),
                                'x-csrf-token': headers["x-csrf-token"],
                                'x-requested-with': headers.get("x-requested-with")
                            }
                            return True
                except:
                    continue
        except Exception as e:
            print(f"Token fetch failed: {e}")
        finally:
            driver.quit()
            
        return False

    def authenticate(self):
        if not self._fetch_token_selenium():
            raise Exception("Failed to authenticate VegasX via Selenium")

    def _get_headers(self):
        if not self.headers:
            self.authenticate()
        return self.headers

    def _check_site_status(self) -> bool:
        try:
            requests.get(self.BASE_URL, timeout=5)
            return True
        except:
            return False

    async def get_agent_balance(self):
        try:
            if not self._check_site_status():
                return None, "Site unreachable"
                
            response = requests.post(self.ENDPOINTS["agent_balance"], headers=self._get_headers(), data="")
            data = response.json()
            
            if "CSRF token mismatch" in data.get("message", ""):
                 self.authenticate()
                 response = requests.post(self.ENDPOINTS["agent_balance"], headers=self._get_headers(), data="")
                 data = response.json()
                 
            if data.get("shop"):
                return float(data.get("shop", {}).get("credits", 0)), "Success"
                
            return None, "Failed to fetch balance"
            
        except Exception as e:
            return None, str(e)

    def _update_user_cache(self):
        payload = "pages%5Bpage%5D=0&pages%5Bpages%5D=1&pages%5Bstart%5D=0&pages%5Bend%5D=1&pages%5Blength%5D=10&pages%5BrecordsTotal%5D=762&pages%5BrecordsDisplay%5D=1&pages%5BserverSide%5D=false"
        response = requests.post(self.ENDPOINTS["user_list"], headers=self._get_headers(), data=payload)
        data = response.json()
        
        if "CSRF token mismatch" in data.get("message", ""):
            self.authenticate()
            response = requests.post(self.ENDPOINTS["user_list"], headers=self._get_headers(), data=payload)
            data = response.json()
            
        if data.get("data"):
            for record in data["data"]:
                email = record.get("email", "").lower()
                self.user_cache[email] = {
                    "userhash": record.get("userhash"),
                    "score": float(record.get("score", 0))
                }

    def _fetch_user_info(self, username: str):
        username = username.lower()
        if username not in self.user_cache:
            self._update_user_cache()
            
        if username not in self.user_cache:
            return None
            
        user_entry = self.user_cache[username]
        player_hash = user_entry["userhash"]
        
        payload = f"userhash={player_hash}&action=7"
        response = requests.post(self.ENDPOINTS["check_player"], headers=self._get_headers(), data=payload)
        data = response.json()
        
        if "CSRF token mismatch" in data.get("message", ""):
             self.authenticate()
             response = requests.post(self.ENDPOINTS["check_player"], headers=self._get_headers(), data=payload)
             data = response.json()

        actual_credits = data.get("actual_credits")
        if actual_credits is not None:
             user_entry["score"] = float(actual_credits)
             return user_entry
             
        return None

    def recharge_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount)

    def redeem_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount)

    def _perform_transaction(self, username: str, amount: float):
        try:
            if not self._check_site_status():
                 return {"status": "error", "message": "Site offline"}
                 
            user_info = self._fetch_user_info(username)
            if not user_info:
                return {"status": "error", "message": "User not found"}
                
            player_hash = user_info["userhash"]
            amount_val = int(float(amount))
            
            if amount_val > 0:
                # Deposit
                payload = f"playerhash={player_hash}&credits={amount_val}00&dik="
                endpoint = self.ENDPOINTS["deposit"]
            else:
                # Withdraw
                payload = f"playerhash={player_hash}&credits={abs(amount_val)}&action=7"
                endpoint = self.ENDPOINTS["withdraw"]
                
            response = requests.post(endpoint, headers=self._get_headers(), data=payload)
            data = response.json()
            
            if data.get("status") == "SUCCESS":
                 return {"status": "success", "message": data.get("data", "Success")}
                 
            return {"status": "error", "message": data.get("data") or data.get("msg", "Failed")}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
