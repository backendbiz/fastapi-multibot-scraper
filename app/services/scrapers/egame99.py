import hashlib
import uuid
import time
import random
import base64
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from app.core.config import settings


class EGame99Scraper:
    DEPOSIT_URL = "https://papi.egame99.vip/fast/user/deposit"
    WITHDRAW_URL = "https://papi.egame99.vip/fast/user/withdrawal"
    CHECK_BALANCE_URL = "https://papi.egame99.vip/fast/user/balance"
    LOGIN_URL = "https://papi.egame99.vip/fast/agent/login"
    SIGNUP_URL = "https://papi.egame99.vip/fast/user/create"
    BASE_URL = "https://pko.egame99.club"
    
    HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}
    
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
        10: "Request ID Used",
        11: "Unknown Database Error",
        12: "User Already Exist",
        13: "Top Up Fail",
        14: "Insufficient Credit",
        15: "Withdrawal Failed",
        16: "Get Balance Failed",
        17: "Operations Not Allowed In Game",
        18: "System Under Maintenance",
        19: "Requested Address Does Not Exist",
        20: "Unknown Error"
    }
    
    GAME_NAME = "egame99"
    GAME_INITIAL = "eg"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or settings.EGAME99_USER
        self.password = password or settings.EGAME99_PASS
        self.request_id = None
        self.timestamp = None
        self.app_id = None
        self.app_secret = None
        self.agent_balance = None

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

    def authenticate(self):
        self._generate_timestamp_and_request_id()

        unsigned_params = self._build_params(account=self.username, passwd=self.password)
        signed_params = self._build_params(
            account=self.username,
            sign=self._generate_signature(unsigned_params, None),
            passwd=self.password
        )

        response = requests.post(self.LOGIN_URL, headers=self.HEADERS, data=signed_params).json()

        if response.get("code") == 200 and response.get("data", {}).get("appid"):
            self.app_id = response["data"]["appid"]
            self.app_secret = self._aes_decrypt(response["data"]["appsecret_encrypted"], self.password)
            self.agent_balance = response["data"]["balance"]
            return self.agent_balance
        else:
            raise Exception("Login failed or invalid response")

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

            balance = self.authenticate()
            return float(balance), "Success"

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
            self._generate_timestamp_and_request_id()

            unsigned_params = self._build_params(account=requested_username, passwd=password)
            signed_params = self._build_params(
                account=requested_username,
                passwd=password,
                sign=self._generate_signature(unsigned_params, self.app_secret)
            )

            response = requests.post(self.SIGNUP_URL, headers=self.HEADERS, data=signed_params).json()

            if response.get("code") == 1 and response.get("data"):
                return {
                    "status": "success",
                    "username": response.get("data", {}).get("full_account", requested_username),
                    "password": password,
                    "message": "User Signed up successfully!"
                }

            error_code = response.get("code", 20)
            return {"status": "error", "message": self.STATUS_CODES.get(error_code, "Unknown error")}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_user_balance(self, username: str):
        self.authenticate()
        self._generate_timestamp_and_request_id()
        
        unsigned_params = self._build_params(account=username)
        signed_params = self._build_params(
            account=username,
            sign=self._generate_signature(unsigned_params, self.app_secret)
        )
        
        response = requests.post(self.CHECK_BALANCE_URL, headers=self.HEADERS, data=signed_params).json()
        return response

    def recharge_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount, "deposit")

    def redeem_user(self, username: str, amount: float):
        return self._perform_transaction(username, amount, "withdraw")

    def _perform_transaction(self, username: str, amount: float, flow_type: str):
        try:
            # Get user balance first
            user_info = self._get_user_balance(username)
            
            if user_info.get('code') != 200:
                error_code = user_info.get('code', 20)
                return {"status": "error", "message": self.STATUS_CODES.get(error_code, "Unknown error")}

            vendor_balance = float(self.agent_balance) if self.agent_balance else 0
            user_balance = float(user_info.get("data", {}).get("balance", 0))
            amount_val = abs(int(float(amount)))

            self._generate_timestamp_and_request_id()
            
            unsigned_params = self._build_params(account=username, amount=str(amount_val))
            signed_params = self._build_params(
                account=username,
                amount=str(amount_val),
                sign=self._generate_signature(unsigned_params, self.app_secret)
            )

            api_url = self.WITHDRAW_URL if flow_type == "withdraw" else self.DEPOSIT_URL
            response = requests.post(api_url, headers=self.HEADERS, data=signed_params).json()

            if response.get("code") == 200:
                return {"status": "success", "message": "Transaction successful"}

            error_code = response.get("code", 20)
            return {"status": "error", "message": self.STATUS_CODES.get(error_code, "Transaction failed")}

        except Exception as e:
            return {"status": "error", "message": str(e)}
