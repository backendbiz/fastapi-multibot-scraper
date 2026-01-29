import hashlib
import uuid
import time
import base64
import random
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from app.core.config import settings


class VBlink777Scraper:
    BASE_URL = "https://www.vblink777.club"
    ENDPOINTS = {
        "login": f"{BASE_URL}/fast/agent/login",
        "balance": f"{BASE_URL}/fast/user/balance",
        "deposit": f"{BASE_URL}/fast/user/deposit",
        "withdraw": f"{BASE_URL}/fast/user/withdrawal",
        "signup": f"{BASE_URL}/fast/user/create"
    }
    GAME_NAME = "vblink777"
    GAME_INITIAL = "vb"
    
    STATUS_CODES = {
        200: "Success",
        1: "New User Is Created",
        2: "User Does Not Exist",
        3: "Parameter Error",
        4: "Invalid Signature or IP blocked",
        5: "Agent Ban",
        6: "Account length error",
        7: "Account format error",
        8: "Password length error",
        9: "Password format error",
        10: "Requestid Used",
        11: "Unknown Database Error",
        12: "User Already Exist",
        13: "Top Up Fail",
        14: "Insufficient Credit",
        15: "Withdrawal Failed",
        16: "Get Balance Failed",
        17: "Operations are Not Allowed In The Game",
        18: "System Is Under Maintenance",
        19: "The Requested Address Does Not Exist",
        20: "Unknown error",
        21: "Error during balance fetch",
        22: "Retry error during transaction"
    }

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.VBLINK777_USER
        self.password = password or settings.VBLINK777_PASS
        self.app_id = None
        self.app_secret = None
        self.agent_balance = None
        self.request_id = None
        self.timestamp = None
        self.headers = {"Content-Type": "application/x-www-form-urlencoded"}

    def _generate_timestamp_and_request_id(self):
        self.request_id = uuid.uuid4().hex[:32]
        self.timestamp = str(int(time.time() * 1000))

    def _aes_decrypt(self, appsecret_encrypted: str, agent_password: str) -> str:
        decoded_data = base64.b64decode(appsecret_encrypted)
        iv = decoded_data[:16]
        encrypted_data = decoded_data[16:]

        agent_password_lower = agent_password.lower()
        key_md5_1 = hashlib.md5(agent_password_lower.encode('utf-8')).hexdigest()
        key_md5_2 = hashlib.md5(key_md5_1.encode('utf-8')).hexdigest()
        aes_key = key_md5_2.encode('utf-8')

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        appsecret = unpadder.update(decrypted_padded_data) + unpadder.finalize()

        return appsecret.decode('utf-8')

    def _generate_signature(self, params: dict, appsecret: str) -> str:
        filtered = {k: v for k, v in params.items() if k != 'sign'}
        sorted_items = sorted(filtered.items())
        param_str = '&'.join(f"{k}={v}" for k, v in sorted_items)
        string_to_sign = param_str + (appsecret or "")
        return hashlib.md5(string_to_sign.encode('utf-8')).hexdigest()

    def _build_params(self, **kwargs) -> dict:
        signature_param = {
            "requestid": self.request_id,
            "timestamp": self.timestamp,
            "account": kwargs.get("account")
        }

        if self.app_id:
            signature_param["appid"] = self.app_id
        if kwargs.get("amount") is not None:
            signature_param["amount"] = kwargs["amount"]
        if kwargs.get("sign") is not None:
            signature_param["sign"] = kwargs["sign"]
        if kwargs.get("passwd") is not None:
            signature_param["passwd"] = kwargs["passwd"]

        return signature_param

    def _check_site_status(self) -> bool:
        try:
            response = requests.get("https://gm.vblink777.club", timeout=10)
            return response.status_code == 200
        except:
            return False

    def authenticate(self):
        self._generate_timestamp_and_request_id()

        unsigned_params = self._build_params(account=self.username, passwd=self.password)
        signed_params = self._build_params(
            account=self.username,
            sign=self._generate_signature(unsigned_params, None),
            passwd=self.password
        )

        response = requests.post(self.ENDPOINTS["login"], headers=self.headers, data=signed_params).json()

        if response.get("code") == 200 and response["data"].get("appid") and response["data"].get("appsecret_encrypted"):
            self.app_id = response["data"]["appid"]
            self.app_secret = self._aes_decrypt(response["data"]["appsecret_encrypted"], self.password)
            self.agent_balance = response["data"]["balance"]
            return float(self.agent_balance)
        else:
            raise Exception("Login failed or invalid response.")

    async def get_agent_balance(self):
        try:
            if not self._check_site_status():
                return None, "Site unreachable"

            balance = self.authenticate()
            return balance, "Success"

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
            password = self._generate_username(fullname)

            # Ensure we're logged in first
            self.authenticate()
            self._generate_timestamp_and_request_id()

            unsigned_params = self._build_params(account=requested_username, passwd=password)
            signed_params = self._build_params(
                account=requested_username,
                passwd=password,
                sign=self._generate_signature(unsigned_params, self.app_secret)
            )

            response = requests.post(self.ENDPOINTS["signup"], headers=self.headers, data=signed_params).json()

            if response.get("code") == 1 and response.get("data"):
                return {
                    "status": "success",
                    "username": response.get("data", {}).get("full_account", requested_username),
                    "password": password,
                    "message": "User Signed up successfully!"
                }

            return {"status": "error", "message": self.STATUS_CODES.get(response.get("code"), "Unknown error")}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_player_balance(self, username: str):
        self._generate_timestamp_and_request_id()
        unsigned_params = self._build_params(account=username)
        signed_params = self._build_params(
            account=username,
            sign=self._generate_signature(unsigned_params, self.app_secret)
        )
        response = requests.post(self.ENDPOINTS["balance"], headers=self.headers, data=signed_params).json()
        return response

    def recharge_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount)

    def redeem_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount)

    def _perform_transaction(self, username: str, amount: float):
        try:
            if not self._check_site_status():
                return {"status": "error", "message": "Site offline"}

            # Login and get balance
            self.authenticate()
            user_info = self._get_player_balance(username)

            if user_info.get("code") != 200:
                return {"status": "error", "message": self.STATUS_CODES.get(user_info.get("code"), "User not found")}

            amount_val = int(float(amount))

            self._generate_timestamp_and_request_id()
            unsigned_params = self._build_params(account=username, amount=str(abs(amount_val)))
            signed_params = self._build_params(
                account=username,
                amount=str(abs(amount_val)),
                sign=self._generate_signature(unsigned_params, self.app_secret)
            )

            endpoint = self.ENDPOINTS["withdraw"] if amount_val < 0 else self.ENDPOINTS["deposit"]
            response = requests.post(endpoint, headers=self.headers, data=signed_params).json()

            if response.get("code") == 200:
                return {"status": "success", "message": response.get("message", "Transaction successful")}

            return {"status": "error", "message": self.STATUS_CODES.get(response.get("code"), "Transaction failed")}

        except Exception as e:
            return {"status": "error", "message": str(e)}
