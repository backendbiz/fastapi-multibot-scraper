import json
import random
import time
import re
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings
from app.services.captcha.captcha import solving_captcha

class Juwa777Scraper:
    BASE_URL = "https://ht.juwa777.com"
    API_ENDPOINTS = {
        "balance": f"{BASE_URL}/api/agent/balance",
        "search_user": f"{BASE_URL}/api/user/userList",
        "recharge": f"{BASE_URL}/api/user/rechargeRedeem",
        "pw_reset": f"{BASE_URL}/api/user/resetUserPwd",
        "signup": f"{BASE_URL}/api/user/addUser"
    }
    REFERER_LINKS = {
        "index": f"{BASE_URL}/HomeDetail",
        "deposit": f"{BASE_URL}/userManagement",
    }
    GAME_INITIAL = "jw"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.JUWA777_USER
        self.password = password or settings.JUWA777_PASS
        self.token = None
        self.cookie = None
        self.driver = None

    def _fill_input_fields(self, driver):
        user_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='text']"))
        )
        pass_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='password']"))
        )
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Sign in')]"))
        )
        captcha_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".loginCode > .el-input__inner"))
        )
        img_element = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".imgCode"))
        )
        
        user_input.click()
        user_input.clear()
        user_input.send_keys(self.username)
        
        pass_input.click()
        pass_input.clear()
        pass_input.send_keys(self.password)
        
        return img_element, login_btn, captcha_field

    def _fetch_token_selenium(self):
        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-gpu")
        # Performance logging for header extraction
        caps = options.to_capabilities()
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}

        driver = uc.Chrome(options=options)
        
        try:
            driver.get(f"{self.BASE_URL}/login")
            WebDriverWait(driver, 10).until(EC.url_to_be(f"{self.BASE_URL}/login"))
            
            img_element, login_btn, captcha_field = self._fill_input_fields(driver)
            
            # Solve Captcha
            result, _ = solving_captcha(driver, None, img_element)
            captcha_field.clear()
            captcha_field.send_keys(result)
            login_btn.click()
            
            # Wait for Login Success
            expected_url = f"{self.BASE_URL}/HomeDetail"
            WebDriverWait(driver, 15).until(EC.url_to_be(expected_url))
            time.sleep(2)  # Wait for network requests
            
            logs = driver.get_log("performance")
            
            for entry in logs:
                try:
                    log = json.loads(entry["message"])["message"]
                    if log["method"] == "Network.requestWillBeSentExtraInfo":
                        headers = log["params"]["headers"]
                        if "Authorization" in headers and "Cookie" in headers:
                            self.token = headers["Authorization"]
                            self.cookie = headers["Cookie"]
                            break
                except:
                    continue
                    
        except Exception as e:
            print(f"Token fetch failed: {e}")
        finally:
            driver.quit()
            
        return self.token and self.cookie

    def authenticate(self):
        if not self._fetch_token_selenium():
            raise Exception("Failed to authenticate Juwa777 via Selenium")

    def _get_headers(self, referer_url: str) -> dict:
        if not self.token or not self.cookie:
            self.authenticate()
        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Authorization': self.token,
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': self.BASE_URL,
            'Referer': referer_url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Cookie': self.cookie
        }
        
    def _fetch_cookie_string(self):
        # Format cookie for JSON payload if needed (replicating original logic)
        filtered_cookie = ""
        if self.cookie:
            match = re.search(r"__cookie\d*=(.*?)(?:;|$)", self.cookie)
            if match:
                filtered_cookie = f'"__cookie": "{match.group(1)}",'
        return filtered_cookie

    def _check_site_status(self) -> bool:
        try:
            response = requests.get(f"{self.BASE_URL}/login", timeout=10)
            return response.status_code == 200
        except:
            return False

    async def get_agent_balance(self):
        try:
            if not self._check_site_status():
                return None, "Site unreachable"
                
            payload = f'{{"locale":"en","timezone":"cst"}}'
            headers = self._get_headers(self.REFERER_LINKS["index"])
            
            response = requests.post(self.API_ENDPOINTS["balance"], headers=headers, data=payload)
            data = response.json()
            
            if data.get("status_code") == 401 or not (data.get("code") == 200 and data.get("data")):
                # Token expired, retry once
                self.authenticate()
                headers = self._get_headers(self.REFERER_LINKS["index"])
                response = requests.post(self.API_ENDPOINTS["balance"], headers=headers, data=payload)
                data = response.json()
                
            if data.get("code") == 200 and data.get("data"):
                 return float(data["data"]["t"]), "Success"
                 
            return None, "Failed to fetch balance"
            
        except Exception as e:
            return None, str(e)

    def _generate_username(self, fullname: str) -> str:
        n = fullname.lower().split()
        base = f"{self.GAME_INITIAL}{n[0][0]}{n[-1][0]}" if n else f"{self.GAME_INITIAL}user"
        base = base[:10]
        username = f"{base}{random.randrange(100):02d}"
        if len(username) < 7:
            username += "".join(str(random.randint(0, 9)) for _ in range(7 - len(username)))
        return username

    def player_signup(self, fullname: str, requested_username: str = None):
        try:
            if not requested_username:
                requested_username = self._generate_username(fullname)
            
            nickname = fullname.replace(" ", "")[:10]
            password = requested_username # Simple password strategy as per original
            
            headers = self._get_headers(self.REFERER_LINKS["deposit"])
            cookie_str = self._fetch_cookie_string()
            
            payload = f'{{"account":"{requested_username}","nickname":"{nickname}","login_pwd":"{password}","check_pwd":"{password}","captcha":null,"t":"",{cookie_str}"locale":"en","timezone":"cst"}}'
            
            response = requests.post(self.API_ENDPOINTS["signup"], headers=headers, data=payload)
            data = response.json()
            
            if data.get("code") == 200 and data.get("msg") == "success":
                return {
                    "status": "success",
                    "username": requested_username,
                    "password": password,
                    "message": "User Signed up successfully!"
                }
            
            return {"status": "error", "message": data.get("msg", "Signup failed")}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_user_info(self, username: str):
        cookie_str = self._fetch_cookie_string()
        payload = f'{{"page":1,"limit":20,"type":1,"search":"{username}","order_by":"desc","sort_field":"register_time",{cookie_str}"locale":"en","timezone":"cst"}}'
        headers = self._get_headers(self.REFERER_LINKS["index"])
        
        response = requests.post(self.API_ENDPOINTS["search_user"], headers=headers, data=payload)
        data = response.json()
        
        if data.get("count", 0) > 0 and data.get("data"):
            for user in data["data"]["list"]:
                if user["login_name"].lower() == username.lower():
                    return user
        return None

    def recharge_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount, "deposit")

    def redeem_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount, "withdraw")

    def _perform_transaction(self, username: str, amount: float, flow_type: str):
        try:
            user_info = self._get_user_info(username)
            if not user_info:
                return {"status": "error", "message": "User not found"}
                
            user_id = user_info["user_id"]
            user_balance = user_info["balance"]
            amount = abs(amount)
            
            opera_type = 2 if flow_type == "withdraw" else 1
            cookie_str = self._fetch_cookie_string()
            
            payload = f'{{"user_id":"{user_id}","type":{opera_type},"account":"{username}","balance":{user_balance},"amount":"{amount}","remark":"","bonusStatus":0, {cookie_str}"locale":"en","timezone":"cst"}}'
            
            headers = self._get_headers(self.REFERER_LINKS["deposit"])
            response = requests.post(self.API_ENDPOINTS["recharge"], headers=headers, data=payload)
            result = response.json()
            
            if result.get("code") == 200 or result.get("status") == 200:
                return {"status": "success", "message": result.get("msg", "Success")}
                
            return {"status": "error", "message": result.get("msg", "Transcation failed")}

        except Exception as e:
            return {"status": "error", "message": str(e)}
