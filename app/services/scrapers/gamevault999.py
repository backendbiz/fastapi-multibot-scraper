import json
import time
import re
import random
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings
from app.services.captcha.captcha import solving_captcha


class GameVault999Scraper:
    BASE_URL = "https://agent.gamevault999.com"
    ENDPOINTS = {
        "balance": f"{BASE_URL}/api/agent/balance",
        "search_user": f"{BASE_URL}/api/user/userList",
        "recharge_redeem": f"{BASE_URL}/api/user/rechargeRedeem",
        "store_const": f"{BASE_URL}/api/agent/StoreConselStat",
        "pw_reset": f"{BASE_URL}/api/user/resetUserPwd",
        "signup": f"{BASE_URL}/api/user/addUser"
    }
    REFERER_LINKS = {
        "deposit_index": f"{BASE_URL}/userManagement",
        "store_const": f"{BASE_URL}/HomeDetail"
    }
    GAME_NAME = "gamevault999"
    GAME_INITIAL = "gv"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.GAMEVAULT999_USER
        self.password = password or settings.GAMEVAULT999_PASS
        self.token = None
        self.cookie = None
        self.agent_id = None

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
            time.sleep(2)
            driver.refresh()
            WebDriverWait(driver, 15).until(EC.url_to_be(expected_url))
            time.sleep(5)

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
            raise Exception("Failed to authenticate GameVault999 via Selenium")
        self._fetch_agent_id()

    def _get_headers(self, referer_url: str) -> dict:
        if not self.token or not self.cookie:
            self.authenticate()
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'authorization': self.token,
            'content-type': 'application/json;charset=UTF-8',
            'cookie': self.cookie,
            'origin': self.BASE_URL,
            'referer': referer_url,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }

    def _fetch_agent_id(self):
        if self.agent_id is None:
            headers = self._get_headers(self.REFERER_LINKS["store_const"])
            payload = '{"locale":"en","timezone":"cst"}'
            response = requests.post(self.ENDPOINTS["store_const"], headers=headers, data=payload)
            data = response.json()
            if data.get("code") == 200:
                self.agent_id = data["data"]["agent_id"]
            else:
                raise Exception(f"Failed to fetch agent_id: {data}")

    def _fetch_cookie_string(self):
        filtered_cookie = ""
        if self.cookie:
            match = re.search(r"__cookie\d*=(.*?)(?:;|$)", self.cookie)
            if match:
                filtered_cookie = f'"__cookie": "{match.group(1)}",'
        return filtered_cookie

    def _check_site_status(self) -> bool:
        try:
            response = requests.get(self.BASE_URL, timeout=10)
            return response.status_code == 200
        except:
            return False

    async def get_agent_balance(self):
        try:
            if not self._check_site_status():
                return None, "Site unreachable"

            headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
            payload = f'{{"agent_id":{self.agent_id},"locale":"en","timezone":"cst"}}'
            response = requests.post(self.ENDPOINTS["balance"], headers=headers, data=payload)
            data = response.json()

            if data.get("status_code") == 401 or not (data.get("code") == 200 and data.get("data")):
                self.authenticate()
                headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
                payload = f'{{"agent_id":{self.agent_id},"locale":"en","timezone":"cst"}}'
                response = requests.post(self.ENDPOINTS["balance"], headers=headers, data=payload)
                data = response.json()

            if data.get("code") == 200 and data.get("data"):
                return float(data["data"]["t"]), "Success"

            return None, "Failed to fetch balance"

        except Exception as e:
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
        try:
            if not requested_username:
                requested_username = self._generate_username(fullname)

            nickname = fullname.replace(" ", "")[:10]
            password = requested_username

            headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
            cookie_str = self._fetch_cookie_string()

            payload = f'{{"account":"{requested_username}","nickname":"{nickname}","rechargeamount":"","login_pwd":"{password}","check_pwd":"{password}","captcha":null,"t":"",{cookie_str}"locale":"en","timezone":"cst"}}'

            response = requests.post(self.ENDPOINTS["signup"], headers=headers, data=payload)
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
        headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
        payload = f'{{"type":1,"search":"{username}","page":1,"limit":20,"locale":"en","timezone":"cst"}}'
        response = requests.post(self.ENDPOINTS["search_user"], headers=headers, data=payload)
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
            amount_val = abs(int(float(amount)))

            opera_type = 1 if flow_type == "deposit" else 2
            cookie_str = self._fetch_cookie_string()

            payload = f'{{"user_id":"{user_id}","type":{opera_type},"account":"{username}","balance":{user_balance},"amount":"{amount_val}","remark":"",{cookie_str}"locale":"en","timezone":"cst"}}'

            headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
            response = requests.post(self.ENDPOINTS["recharge_redeem"], headers=headers, data=payload)
            result = response.json()

            if result.get("code") == 200 and "The balance is not below the limit" not in result.get("msg", ""):
                return {"status": "success", "message": result.get("msg", "Success")}

            return {"status": "error", "message": result.get("msg", "Transaction failed")}

        except Exception as e:
            return {"status": "error", "message": str(e)}
