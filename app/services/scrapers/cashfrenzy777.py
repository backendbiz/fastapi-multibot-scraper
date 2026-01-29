import json
import time
import random
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings


class CashFrenzy777Scraper:
    BASE_URL = "https://agentserver.cashfrenzy777.com"
    ENDPOINTS = {
        "balance": f"{BASE_URL}/api/agent/getMoney",
        "search_user": f"{BASE_URL}/api/player/userList?page=1&limit=20&search_type=1&search_content=",
        "recharge_user": f"{BASE_URL}/api/player/agentRecharge",
        "withdraw_user": f"{BASE_URL}/api/player/agentWithdraw",
        "pw_reset": f"{BASE_URL}/api/player/reset",
        "signup": f"{BASE_URL}/api/player/playerInsert"
    }
    REFERER_LINKS = {
        "index": f"{BASE_URL}/admin/player/index",
        "deposit": f"{BASE_URL}/admin/player/recharge",
        "withdraw": f"{BASE_URL}/admin/player/withdraw",
        "pw_reset": f"{BASE_URL}/admin/player/resetpw",
        "signup": f"{BASE_URL}/admin/player/insert"
    }
    GAME_NAME = "cashfrenzy777"
    GAME_INITIAL = "cf"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.CASHFRENZY777_USER
        self.password = password or settings.CASHFRENZY777_PASS
        self.token = None
        self.cookie = None

    def _fill_input_fields(self, driver):
        user_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='text' and @name='username']"))
        )
        pass_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='password' and @name='password']"))
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
            driver.get(f"{self.BASE_URL}/admin/login")
            WebDriverWait(driver, 15).until(EC.url_contains("login"))

            login_btn = self._fill_input_fields(driver)
            login_btn.click()

            expected_url = f"{self.BASE_URL}/admin/index"
            WebDriverWait(driver, 20).until(EC.url_to_be(expected_url))
            time.sleep(2)
            driver.refresh()
            WebDriverWait(driver, 20).until(EC.url_to_be(expected_url))
            time.sleep(3)

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
            raise Exception("Failed to authenticate CashFrenzy777 via Selenium")

    def _get_headers(self, referer_url: str) -> dict:
        if not self.token or not self.cookie:
            self.authenticate()
        return {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'en-US,en;q=0.9',
            'authorization': self.token,
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': self.BASE_URL,
            'referer': referer_url,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'x-requested-with': 'XMLHttpRequest',
            'Cookie': self.cookie
        }

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

            headers = self._get_headers(self.REFERER_LINKS["index"])
            response = requests.post(self.ENDPOINTS["balance"], headers=headers)
            data = response.json()

            if not (data.get("status_code") == 200 and data.get("data")):
                self.authenticate()
                headers = self._get_headers(self.REFERER_LINKS["index"])
                response = requests.post(self.ENDPOINTS["balance"], headers=headers)
                data = response.json()

            if data.get("status_code") == 200 and data.get("data"):
                return float(data["data"]), "Success"

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

            nickname = fullname.replace(" ", "")[:15]
            password = requested_username

            headers = self._get_headers(self.REFERER_LINKS["signup"])
            payload = f"username={requested_username}&nickname={nickname}&money=&password={password}&password_confirmation={password}"

            response = requests.post(self.ENDPOINTS["signup"], headers=headers, data=payload)
            data = response.json()

            if data.get("status_code") == 200 and data.get("message") and data.get("data"):
                return {
                    "status": "success",
                    "username": data["data"]["account"],
                    "password": data["data"]["password"],
                    "message": "User Signed up successfully!"
                }

            return {"status": "error", "message": data.get("message", "Signup failed")}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_user_info(self, username: str):
        headers = self._get_headers(self.REFERER_LINKS["index"])
        response = requests.get(self.ENDPOINTS["search_user"] + username, headers=headers)
        data = response.json()

        if data.get("data"):
            for user in data.get("data", []):
                if user["Account"].lower() == username.lower():
                    return user
        return None

    def recharge_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount, "deposit")

    def redeem_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount, "withdraw")

    def _perform_transaction(self, username: str, amount: float, flow_type: str):
        try:
            # Get agent balance first
            headers = self._get_headers(self.REFERER_LINKS["index"])
            balance_response = requests.post(self.ENDPOINTS["balance"], headers=headers)
            balance_data = balance_response.json()
            vendor_balance = float(balance_data.get("data", 0)) if balance_data.get("status_code") == 200 else 0

            user_info = self._get_user_info(username)
            if not user_info:
                return {"status": "error", "message": "User not found"}

            user_id = user_info["Id"]
            user_balance = float(user_info["score"])
            amount_val = abs(int(float(amount)))

            if flow_type == "deposit":
                opera_type = 0
                key = "available_balance"
                balance_val = vendor_balance
                endpoint = self.ENDPOINTS["recharge_user"]
            else:
                opera_type = 1
                key = "customer_balance"
                balance_val = user_balance
                endpoint = self.ENDPOINTS["withdraw_user"]

            payload = f"id={user_id}&{key}={balance_val}&opera_type={opera_type}&balance={amount_val}&remark="

            headers = self._get_headers(self.REFERER_LINKS[flow_type])
            response = requests.post(endpoint, headers=headers, data=payload)
            result = response.json()

            if result.get("status_code") == 200:
                return {"status": "success", "message": result.get("message", "Success")}

            return {"status": "error", "message": result.get("message", "Transaction failed")}

        except Exception as e:
            return {"status": "error", "message": str(e)}
