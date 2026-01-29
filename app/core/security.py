"""
Security utilities for API key encryption and decryption.
Uses AES-256-GCM for secure symmetric encryption.
"""
import base64
import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

logger = logging.getLogger(__name__)


class APIKeyEncryption:
    """
    Handles API key encryption and decryption using AES-256-GCM.
    
    The encrypted format is: base64(nonce + ciphertext + tag)
    - nonce: 12 bytes (96 bits) - randomly generated for each encryption
    - ciphertext: variable length - the encrypted API key
    - tag: 16 bytes (128 bits) - authentication tag
    """

    NONCE_SIZE = 12  # 96 bits for GCM
    KEY_SIZE = 32    # 256 bits for AES-256

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize with a secret key.
        
        Args:
            secret_key: Hex-encoded 32-byte secret key. If not provided,
                       uses API_KEY_SECRET from settings.
        """
        self.secret_key = secret_key or settings.API_KEY_SECRET
        self._derive_key()

    def _derive_key(self) -> None:
        """Derive a 256-bit key from the secret using SHA-256."""
        # Use SHA-256 to ensure we have exactly 32 bytes
        self.key = hashlib.sha256(self.secret_key.encode()).digest()
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt an API key.
        
        Args:
            plaintext: The API key to encrypt
            
        Returns:
            Base64-encoded encrypted string (nonce + ciphertext + tag)
        """
        nonce = os.urandom(self.NONCE_SIZE)
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode(), None)
        
        # Combine nonce and ciphertext, then base64 encode
        encrypted = base64.urlsafe_b64encode(nonce + ciphertext).decode()
        return encrypted

    def decrypt(self, encrypted: str) -> Optional[str]:
        """
        Decrypt an encrypted API key.
        
        Args:
            encrypted: Base64-encoded encrypted string
            
        Returns:
            Decrypted API key or None if decryption fails
        """
        try:
            # Decode from base64
            data = base64.urlsafe_b64decode(encrypted.encode())
            
            # Extract nonce and ciphertext
            nonce = data[:self.NONCE_SIZE]
            ciphertext = data[self.NONCE_SIZE:]
            
            # Decrypt
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode()
            
        except Exception as e:
            logger.warning(f"Failed to decrypt API key: {e}")
            return None

    @staticmethod
    def generate_api_key(prefix: str = "sk", length: int = 32) -> str:
        """
        Generate a new random API key.
        
        Args:
            prefix: Prefix for the API key (e.g., 'sk' for secret key)
            length: Length of the random part in bytes
            
        Returns:
            A new API key in format: prefix_randomhex
        """
        random_part = secrets.token_hex(length)
        return f"{prefix}_{random_part}"


class APIKeyValidator:
    """Validates API keys against configured valid keys."""

    def __init__(self):
        self.encryption = APIKeyEncryption()
        self._valid_keys = set(settings.get_valid_api_keys())

    def validate(self, api_key: str, encrypted: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Validate an API key.
        
        Args:
            api_key: The API key to validate (may be encrypted)
            encrypted: Whether the key needs to be decrypted first
            
        Returns:
            Tuple of (is_valid, decrypted_key or None)
        """
        decrypted_key = api_key

        # Try to decrypt if encrypted flag is set
        if encrypted:
            decrypted = self.encryption.decrypt(api_key)
            if decrypted:
                decrypted_key = decrypted
            # If decryption fails, try using the key as-is (for dev mode)

        # Check if key is in valid keys list
        is_valid = decrypted_key in self._valid_keys

        # In development, also accept unencrypted keys directly
        if not is_valid and settings.ENVIRONMENT == "development":
            is_valid = api_key in self._valid_keys

        return is_valid, decrypted_key if is_valid else None

    def add_key(self, key: str) -> None:
        """Add a new valid key (runtime only, not persisted)."""
        self._valid_keys.add(key)

    def remove_key(self, key: str) -> None:
        """Remove a valid key (runtime only, not persisted)."""
        self._valid_keys.discard(key)


# Global instances
api_key_encryption = APIKeyEncryption()
api_key_validator = APIKeyValidator()
