import json
import re
import time
import random
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings


class LasVegasSweepsScraper:
    BASE_URL = "https://agent.lasvegassweeps.com"
    ENDPOINTS = {
        "balance": f"{BASE_URL}/api/agent/balance",
        "search_user": f"{BASE_URL}/api/user/userList",
        "recharge_redeem_user": f"{BASE_URL}/api/user/rechargeRedeem",
        "search_agent": f"{BASE_URL}/api/agent/agentList",
        "pw_reset": f"{BASE_URL}/api/user/resetUserPwd",
        "signup": f"{BASE_URL}/api/user/addUser"
    }
    REFERER_LINKS = {
        "deposit_index": f"{BASE_URL}/userManagement",
        "agent_index": f"{BASE_URL}/adminList"
    }
    GAME_NAME = "lasvegassweeps"
    GAME_INITIAL = "vs"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.LASVEGASSWEEPS_USER
        self.password = password or settings.LASVEGASSWEEPS_PASS
        self.token = None
        self.cookie = None
        self.agent_id = None

    def _fill_input_fields(self, driver):
        user_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='text' and @placeholder='Account']"))
        )
        pass_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='password' and @placeholder='Password']"))
        )
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
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
            WebDriverWait(driver, 15).until(EC.url_contains("login"))

            login_btn = self._fill_input_fields(driver)
            login_btn.click()

            # Wait for redirect to dashboard
            WebDriverWait(driver, 20).until(
                lambda d: "login" not in d.current_url.lower()
            )
            time.sleep(3)
            driver.refresh()
            time.sleep(3)

            logs = driver.get_log("performance")

            for entry in logs:
                try:
                    log = json.loads(entry["message"])["message"]
                    if log["method"] == "Network.requestWillBeSentExtraInfo":
                        headers = log["params"]["headers"]
                        if "authorization" in headers and "cookie" in headers:
                            self.token = headers["authorization"]
                            self.cookie = headers["cookie"]
                            break
                        elif "Authorization" in headers and "Cookie" in headers:
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
            raise Exception("Failed to authenticate LasVegasSweeps via Selenium")
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

    def _fetch_cookie_value(self) -> str:
        if self.cookie:
            match = re.search(r"__cookie\d*=(.*?)(?:;|$)", self.cookie)
            if match:
                return f'"__cookie": "{match.group(1)}",'
        return ""

    def _fetch_agent_id(self):
        if self.agent_id is None:
            headers = self._get_headers(self.REFERER_LINKS["agent_index"])
            payload = json.dumps({
                "limit": 20,
                "locale": "en",
                "page": "1",
                "search": "",
                "timezone": "cst",
                "type": ""
            })
            response = requests.post(self.ENDPOINTS["search_agent"], headers=headers, data=payload)
            data = response.json()
            if data.get("code") == 200 and data.get("data", {}).get("list"):
                self.agent_id = data["data"]["list"][0]["agent_id"]
            else:
                raise Exception(f"Failed to fetch agent_id: {data}")

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
            payload = json.dumps({
                "agent_id": self.agent_id,
                "locale": "en",
                "timezone": "cst"
            })
            response = requests.post(self.ENDPOINTS["balance"], headers=headers, data=payload)
            data = response.json()

            if not (data.get("code") == 200 and data.get("data")) or data.get("status_code") == 401:
                self.authenticate()
                headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
                payload = json.dumps({
                    "agent_id": self.agent_id,
                    "locale": "en",
                    "timezone": "cst"
                })
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

            password = requested_username
            cookie_value = self._fetch_cookie_value()

            headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
            payload = json.dumps({
                "account": requested_username,
                "nickname": fullname,
                "rechargeamount": "",
                "login_pwd": password,
                "check_pwd": password,
                "captcha": None,
                "t": "",
                "locale": "en",
                "timezone": "cst"
            })

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
        payload = json.dumps({
            "type": 1,
            "search": username,
            "page": 1,
            "limit": 20,
            "locale": "en",
            "timezone": "cst"
        })
        response = requests.post(self.ENDPOINTS["search_user"], headers=headers, data=payload)
        data = response.json()

        if data.get("count", 0) > 0 and data.get("data", {}).get("list"):
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
            # Get agent balance first
            headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
            balance_payload = json.dumps({
                "agent_id": self.agent_id,
                "locale": "en",
                "timezone": "cst"
            })
            balance_response = requests.post(self.ENDPOINTS["balance"], headers=headers, data=balance_payload)
            balance_data = balance_response.json()
            vendor_balance = float(balance_data.get("data", {}).get("t", 0)) if balance_data.get("code") == 200 else 0

            user_info = self._get_user_info(username)
            if not user_info:
                return {"status": "error", "message": "User not found"}

            user_id = user_info["user_id"]
            user_balance = float(user_info["balance"])
            amount_val = abs(int(float(amount)))

            opera_type = 1 if flow_type == "deposit" else 2

            payload = json.dumps({
                "user_id": str(user_id),
                "type": opera_type,
                "account": username,
                "balance": user_balance,
                "amount": str(amount_val),
                "remark": "",
                "locale": "en",
                "timezone": "cst"
            })

            headers = self._get_headers(self.REFERER_LINKS["deposit_index"])
            response = requests.post(self.ENDPOINTS["recharge_redeem_user"], headers=headers, data=payload)
            result = response.json()

            if result.get("code") == 200 and "The balance is not below the limit" not in result.get("msg", ""):
                return {"status": "success", "message": result.get("msg", "Success")}

            return {"status": "error", "message": result.get("msg", "Transaction failed")}

        except Exception as e:
            return {"status": "error", "message": str(e)}
