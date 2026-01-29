#!/usr/bin/env python3
"""
Script to generate and encrypt API keys.
Run this script to create new API keys for your application.

Usage:
    python scripts/generate_api_key.py
    python scripts/generate_api_key.py --name "production-key"
    python scripts/generate_api_key.py --secret "your-custom-secret"
"""
import argparse
import hashlib
import os
import secrets
import sys
from base64 import urlsafe_b64encode

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("Error: cryptography package not installed.")
    print("Install with: pip install cryptography")
    sys.exit(1)


def generate_secret_key() -> str:
    """Generate a new 32-byte secret key for API key encryption."""
    return secrets.token_hex(32)


def generate_api_key(prefix: str = "sk", length: int = 32) -> str:
    """Generate a new random API key."""
    random_part = secrets.token_hex(length)
    return f"{prefix}_{random_part}"


def encrypt_api_key(plain_key: str, secret: str) -> str:
    """Encrypt an API key using AES-256-GCM."""
    # Derive 256-bit key from secret
    key = hashlib.sha256(secret.encode()).digest()
    aesgcm = AESGCM(key)
    
    # Generate random nonce
    nonce = os.urandom(12)
    
    # Encrypt
    ciphertext = aesgcm.encrypt(nonce, plain_key.encode(), None)
    
    # Return base64 encoded result
    return urlsafe_b64encode(nonce + ciphertext).decode()


def main():
    parser = argparse.ArgumentParser(
        description="Generate and encrypt API keys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate a new API key with auto-generated secret
    python scripts/generate_api_key.py

    # Generate with a custom name
    python scripts/generate_api_key.py --name "my-app-key"

    # Use existing secret (for consistency)
    python scripts/generate_api_key.py --secret "your-existing-secret"

    # Just generate a new secret key
    python scripts/generate_api_key.py --secret-only
        """,
    )
    
    parser.add_argument(
        "--name",
        default="api-key",
        help="Name/label for the API key (default: api-key)",
    )
    parser.add_argument(
        "--secret",
        help="API_KEY_SECRET to use for encryption (generates new if not provided)",
    )
    parser.add_argument(
        "--prefix",
        default="sk",
        help="Prefix for the API key (default: sk)",
    )
    parser.add_argument(
        "--secret-only",
        action="store_true",
        help="Only generate a new secret key",
    )
    
    args = parser.parse_args()
    
    # Generate secret only mode
    if args.secret_only:
        new_secret = generate_secret_key()
        print("\n" + "=" * 60)
        print("Generated Secret Key (API_KEY_SECRET)")
        print("=" * 60)
        print(f"\n{new_secret}\n")
        print("Add this to your .env file:")
        print(f"API_KEY_SECRET={new_secret}")
        print("=" * 60 + "\n")
        return
    
    # Use provided secret or generate new
    secret = args.secret or generate_secret_key()
    
    # Generate API key
    plain_key = generate_api_key(prefix=args.prefix)
    
    # Encrypt the key
    encrypted_key = encrypt_api_key(plain_key, secret)
    
    # Print results
    print("\n" + "=" * 60)
    print(f"Generated API Key: {args.name}")
    print("=" * 60)
    
    if not args.secret:
        print(f"\n⚠️  New API_KEY_SECRET generated (save this!):")
        print(f"   {secret}\n")
    
    print(f"Plain Key (store securely, shown only once!):")
    print(f"   {plain_key}\n")
    
    print(f"Encrypted Key (use in X-API-Key header):")
    print(f"   {encrypted_key}\n")
    
    print("=" * 60)
    print("\nEnvironment variables to add:\n")
    if not args.secret:
        print(f"API_KEY_SECRET={secret}")
    print(f"VALID_API_KEYS={plain_key}")
    print("\n" + "=" * 60)
    print("\nUsage example with curl:\n")
    print(f'curl -H "X-API-Key: {encrypted_key}" http://localhost:8000/api/v1/items')
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
