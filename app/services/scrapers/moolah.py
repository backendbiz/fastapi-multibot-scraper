import base64
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
    Moolah Scraper - Full Selenium automation with captcha solving.
    Uses CapSolver and 2Captcha APIs for captcha resolution.
    """
    BASE_URL = "https://moolah.vip:8781"
    CHECK_URL = "https://milkywayapp.xyz:8033/ws/service.ashx"
    LOGIN_ENDPOINT = "/default.aspx"
    DASHBOARD_ENDPOINT = "/Store.aspx"
    GAME_NAME = "moolah"
    GAME_INITIAL = "mh"

    # Timeouts
    TIMEOUT = 3
    LONG_TIMEOUT = 7
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
        self.capsolver_api = getattr(settings, 'CAPSOLVER_API', None)
        self.twocaptcha_api = getattr(settings, 'TWOCAPTCHA_API', None)
        self.driver = None
        self.wait = None
        self.account_position = 2
        self.restart_required = False

    def _initialize_driver(self):
        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-gpu")
        self.driver = uc.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10, poll_frequency=1)

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _get_element(self, locator_key, timeout=None):
        t = timeout if timeout else self.TIMEOUT
        return WebDriverWait(self.driver, t).until(
            EC.element_to_be_clickable(self.LOCATORS[locator_key])
        )

    def _wait_visible(self, locator_key, timeout=None):
        t = timeout if timeout else self.TIMEOUT
        return WebDriverWait(self.driver, t).until(
            EC.visibility_of_element_located(self.LOCATORS[locator_key])
        )

    def _switch_to_default_frame(self):
        self.driver.switch_to.default_content()

    def _switch_to_main_frame(self):
        WebDriverWait(self.driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it(self.LOCATORS['main_iframe'])
        )

    def _switch_to_nested_iframe(self):
        """Switch to the 4th iframe used for actions."""
        self._switch_to_default_frame()
        WebDriverWait(self.driver, self.LONG_TIMEOUT).until(
            lambda d: len(d.find_elements(By.TAG_NAME, "iframe")) >= 4
        )
        target_frame = WebDriverWait(self.driver, self.TIMEOUT).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "iframe"))
        )[3]
        self.driver.switch_to.frame(target_frame)

    def _capsolver_request(self, screenshot_data):
        """Use CapSolver API to solve captcha."""
        if not self.capsolver_api:
            return None, False, False

        try:
            import capsolver
            capsolver.api_key = self.capsolver_api
            encoded_string = base64.b64encode(screenshot_data).decode("utf-8")
            result = capsolver.solve({
                "type": "ImageToTextTask",
                "module": "common",
                "body": encoded_string,
                "case": False
            })

            if (result.get("text") and not result.get("text").isdigit()) or \
               (result.get("answers") and not result.get("answers")[0].isdigit()):
                return result, False, True

            if (result.get("confidence") and result["confidence"] > 0.8) or \
               (result.get("answers") and len(result["answers"][0]) >= 4):
                if result.get('text'):
                    return result["text"], True, False
                elif result.get('answers'):
                    return result["answers"][0], True, False

            return result, False, False
        except Exception as e:
            print(f"CapSolver error: {e}")
            return None, False, False

    def _twocaptcha_request(self, screenshot_data):
        """Use 2Captcha API to solve captcha."""
        if not self.twocaptcha_api:
            return None, False, False

        try:
            # Save screenshot temporarily
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(screenshot_data)
                captcha_file = f.name

            with open(captcha_file, 'rb') as f:
                response = requests.post(
                    'https://2captcha.com/in.php',
                    files={'file': f},
                    data={'key': self.twocaptcha_api, 'method': 'post'}
                )

            task_id = response.text.split('|')[1]

            # Poll for result
            for _ in range(3):
                response = requests.get(
                    f'https://2captcha.com/res.php?key={self.twocaptcha_api}&action=get&id={task_id}'
                )
                if response.text == 'CAPCHA_NOT_READY':
                    time.sleep(5)
                    continue
                else:
                    captcha_text = response.text.split('|')[1]
                    break
            else:
                return None, False, False

            import os
            os.remove(captcha_file)

            if not captcha_text.isdigit():
                return captcha_text, False, True
            return captcha_text, True, False

        except Exception as e:
            print(f"2Captcha error: {e}")
            return None, False, False

    def _solve_captcha(self, img_element):
        """Attempt to solve captcha using available APIs."""
        for _ in range(2):
            screenshot_data = img_element.screenshot_as_png

            # Try CapSolver first
            result, success, restart = self._capsolver_request(screenshot_data)
            if success:
                return result, False

            # Fallback to 2Captcha
            result, success, restart = self._twocaptcha_request(screenshot_data)
            if success:
                return result, False

            if restart:
                return None, True

            # Refresh captcha and retry
            img_element.click()
            time.sleep(1)

        return None, True

    def _login(self):
        """Perform login with captcha solving."""
        self.restart_required = False
        self.driver.get(f"{self.BASE_URL}{self.LOGIN_ENDPOINT}")

        if not self.username or not self.password:
            return False

        for attempt in range(self.MAX_RETRIES):
            try:
                self._switch_to_default_frame()

                el = self._wait_visible('username')
                el.clear()
                el.send_keys(self.username)

                el = self._wait_visible('password')
                el.clear()
                el.send_keys(self.password)

                self._wait_visible('captcha_input')
                img_element = self._wait_visible('captcha_img')

                captcha_result, self.restart_required = self._solve_captcha(img_element)

                if self.restart_required or not captcha_result:
                    return False

                self.driver.find_element(*self.LOCATORS['captcha_input']).send_keys(captcha_result)
                self._get_element('login_btn').click()

                try:
                    raw_msg = WebDriverWait(self.driver, self.TIMEOUT).until(
                        EC.presence_of_element_located(self.LOCATORS['mb_msg'])
                    ).text
                    if "incorrect" in raw_msg.lower():
                        break
                except:
                    pass

                WebDriverWait(self.driver, self.TIMEOUT).until(
                    EC.url_to_be(f"{self.BASE_URL}{self.DASHBOARD_ENDPOINT}")
                )

                try:
                    self._get_element('alert_ok', timeout=4).click()
                except:
                    pass

                return True

            except Exception as e:
                print(f"Login attempt {attempt + 1} failed: {e}")
                time.sleep(1)
                self.driver.get(f"{self.BASE_URL}{self.LOGIN_ENDPOINT}")

        return False

    def _check_session_timeout(self):
        """Check and refresh session if needed."""
        self.driver.refresh()
        try:
            self._get_element('alert_ok', timeout=4).click()
        except:
            pass

        dashboard_url = f"{self.BASE_URL}{self.DASHBOARD_ENDPOINT}"

        try:
            time.sleep(1)
            if self.driver.current_url != dashboard_url:
                return self._login()
            return True
        except Exception as e:
            print(f"Session check failed: {e}")
            return False

    def _check_site_status(self) -> bool:
        try:
            response = requests.get(self.CHECK_URL, timeout=10)
            return response.status_code == 200
        except:
            return False

    async def get_agent_balance(self):
        """Fetch agent balance."""
        try:
            if not self._check_site_status():
                return None, "Site unreachable"

            self._initialize_driver()

            if not self._login():
                self.close()
                return None, "Login failed"

            try:
                if self._check_session_timeout():
                    self._switch_to_default_frame()
                    result = WebDriverWait(self.driver, self.TIMEOUT).until(
                        EC.presence_of_element_located(self.LOCATORS['agent_bln'])
                    ).text
                    result = result.split(':')[-1].strip()
                    self.close()
                    return float(result), "Success"
                else:
                    self.close()
                    return None, "Session issue"
            except Exception as e:
                self.close()
                return None, str(e)

        except Exception as e:
            self.close()
            return None, str(e)

    def _generate_username(self, fullname: str) -> str:
        n = fullname.lower().split()
        base = f"{self.GAME_INITIAL}{n[0]}{n[-1][0]}" if n else f"{self.GAME_INITIAL}user"
        base = base[:10]
        username = f"{base}{random.randrange(100):02d}"
        if len(username) < 7:
            username += "".join(str(random.randint(0, 9)) for _ in range(7 - len(username)))
        return username

    def _verify_user_in_table(self, target_username: str) -> bool:
        """Verify user exists in the table."""
        target_username = str(target_username).lower()
        self.account_position = 2

        for attempt in range(self.MAX_RETRIES):
            try:
                self._switch_to_main_frame()

                search_field = self._get_element('search_input')
                search_field.clear()
                search_field.send_keys(target_username)
                self._get_element('search_btn').click()

                for count in range(1, 6):
                    try:
                        xpath = f"//table[@id='item']/tbody/tr[{self.account_position}]/td[3]"
                        fetched_user = WebDriverWait(self.driver, 5).until(
                            EC.visibility_of_element_located((By.XPATH, xpath))
                        ).text.strip()

                        if fetched_user.lower() == target_username:
                            self._switch_to_default_frame()
                            return True

                        self.account_position += 1
                        self._get_element('search_btn').click()
                        time.sleep(0.3)
                    except:
                        break

                self._switch_to_default_frame()
                self.driver.refresh()
                time.sleep(1)

            except Exception as e:
                self._switch_to_default_frame()
                self._check_session_timeout()
                print(f"Verification error: {e}")

        return False

    def _get_balance_and_verify(self, target_username: str):
        """Get user balance after verification."""
        self._switch_to_main_frame()

        table_user = WebDriverWait(self.driver, self.TIMEOUT).until(
            EC.presence_of_element_located(
                (By.XPATH, f"//table[@id='item']/tbody/tr[{self.account_position}]/td[3]")
            )
        ).text

        WebDriverWait(self.driver, self.TIMEOUT).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//table[@id='item']/tbody/tr[{self.account_position}]/td/a")
            )
        ).click()

        detail_name = WebDriverWait(self.driver, self.TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, "//span[@id='txtAccount']"))
        ).text

        if table_user != detail_name:
            self._switch_to_default_frame()
            if self._verify_user_in_table(target_username):
                return self._get_balance_and_verify(target_username)

        WebDriverWait(self.driver, self.TIMEOUT).until(
            lambda d: d.find_element(By.XPATH, "//span[@id='txtBalance']").text.strip() != ""
        )
        balance = float(self.driver.find_element(By.XPATH, "//span[@id='txtBalance']").text)

        self._switch_to_default_frame()
        return detail_name, balance

    def player_signup(self, fullname: str, requested_username: str = None):
        """Sign up a new player."""
        try:
            self._initialize_driver()

            if not self._login():
                self.close()
                return {"status": "error", "message": "Login failed"}

            if not requested_username:
                requested_username = self._generate_username(fullname)

            nickname = fullname.replace(" ", "_")
            password = self._generate_username(fullname)

            for _ in range(self.MAX_RETRIES):
                try:
                    if not self._check_session_timeout():
                        raise Exception("Session error")

                    try:
                        self._get_element('alert_ok', 4).click()
                    except:
                        pass

                    self._switch_to_main_frame()
                    self._get_element('create_player_link').click()

                    self._switch_to_nested_iframe()

                    self._get_element('signup_acc').send_keys(requested_username)
                    self._get_element('signup_nick').send_keys(nickname)
                    self._get_element('signup_pass').send_keys(password)
                    self._get_element('signup_pass2').send_keys(password)

                    self._get_element('create_player_link').click()

                    self._switch_to_default_frame()
                    raw_msg = WebDriverWait(self.driver, self.TIMEOUT).until(
                        EC.presence_of_element_located(self.LOCATORS['mb_msg'])
                    ).text
                    self._get_element('mb_ok').click()

                    if "Added successfully" in raw_msg:
                        self.close()
                        return {
                            "status": "success",
                            "username": requested_username,
                            "password": password,
                            "message": "User Signed up successfully!"
                        }
                    elif "nickname already exists" in raw_msg:
                        self.close()
                        return {"status": "error", "message": "Nickname already exists"}
                    elif "account number already exists" in raw_msg:
                        self.close()
                        return {"status": "error", "message": "Username already exists"}
                    else:
                        self.close()
                        return {"status": "error", "message": raw_msg}

                except Exception as e:
                    print(f"Signup error: {e}")

            self.close()
            return {"status": "error", "message": "Signup failed after retries"}

        except Exception as e:
            self.close()
            return {"status": "error", "message": str(e)}

    def _perform_transaction_flow(self, amount: float, note: str, flow_type: str):
        """Perform recharge or redeem transaction."""
        try:
            self._switch_to_main_frame()
            link_text = 'Recharge' if flow_type == 'recharge' else 'Redeem'
            WebDriverWait(self.driver, self.TIMEOUT).until(
                EC.element_to_be_clickable((By.LINK_TEXT, link_text))
            ).click()

            self._switch_to_nested_iframe()

            add_gold = self._get_element('add_gold')
            add_gold.clear()
            add_gold.send_keys(str(abs(int(amount))))

            self._get_element('note').send_keys(note)
            self._get_element('submit_btn').click()

            self._switch_to_default_frame()
            raw_msg = WebDriverWait(self.driver, self.TIMEOUT).until(
                EC.presence_of_element_located(self.LOCATORS['mb_msg'])
            ).text
            self._get_element('mb_ok').click()

            if "Confirmed successful" in raw_msg:
                return True, raw_msg
            return False, raw_msg

        except Exception as e:
            return False, str(e)

    def recharge_user(self, username: str, amount: float):
        """Recharge/deposit for a user."""
        try:
            self._initialize_driver()

            if not self._login():
                self.close()
                return {"status": "error", "message": "Login failed"}

            amount_val = abs(int(float(amount)))

            if not self._verify_user_in_table(username):
                self.close()
                return {"status": "error", "message": "User not found"}

            detail_name, before_balance = self._get_balance_and_verify(username)
            if detail_name.lower() != username.lower():
                self.close()
                return {"status": "error", "message": "Username mismatch"}

            self._switch_to_default_frame()
            success, message = self._perform_transaction_flow(amount_val, "bot-deposit", "recharge")

            if success:
                try:
                    self._switch_to_main_frame()
                    WebDriverWait(self.driver, self.TIMEOUT).until(
                        lambda d: d.find_element(By.XPATH, "//span[@id='txtBalance']").text.strip() != ""
                    )
                    after_balance = float(self.driver.find_element(By.XPATH, "//span[@id='txtBalance']").text)
                except:
                    after_balance = before_balance + amount_val

                self.close()
                return {
                    "status": "success",
                    "message": message,
                    "before_balance": before_balance,
                    "after_balance": after_balance
                }

            self.close()
            return {"status": "error", "message": message}

        except Exception as e:
            self.close()
            return {"status": "error", "message": str(e)}

    def redeem_user(self, username: str, amount: float):
        """Redeem/withdraw for a user."""
        try:
            self._initialize_driver()

            if not self._login():
                self.close()
                return {"status": "error", "message": "Login failed"}

            amount_val = abs(int(float(amount)))

            if not self._verify_user_in_table(username):
                self.close()
                return {"status": "error", "message": "User not found"}

            detail_name, before_balance = self._get_balance_and_verify(username)
            if detail_name.lower() != username.lower():
                self.close()
                return {"status": "error", "message": "Username mismatch"}

            if before_balance < amount_val:
                self.close()
                return {"status": "error", "message": "Insufficient player balance"}

            self._switch_to_default_frame()
            success, message = self._perform_transaction_flow(amount_val, "bot-redeem", "redeem")

            if success:
                try:
                    self._switch_to_main_frame()
                    WebDriverWait(self.driver, self.TIMEOUT).until(
                        lambda d: d.find_element(By.XPATH, "//span[@id='txtBalance']").text.strip() != ""
                    )
                    after_balance = float(self.driver.find_element(By.XPATH, "//span[@id='txtBalance']").text)
                except:
                    after_balance = before_balance - amount_val

                self.close()
                return {
                    "status": "success",
                    "message": message,
                    "before_balance": before_balance,
                    "after_balance": after_balance
                }

            self.close()
            return {"status": "error", "message": message}

        except Exception as e:
            self.close()
            return {"status": "error", "message": str(e)}
