"""
API Key management endpoints.
Generate, encrypt, decrypt, and validate API keys.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status

from app.core.security import APIKeyEncryption, api_key_encryption, api_key_validator
from app.schemas import (
    APIKeyCreate,
    APIKeyDecrypt,
    APIKeyDecryptResponse,
    APIKeyResponse,
    ErrorResponse,
    SuccessResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/keys/generate",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new API key",
    description="Generate a new API key with optional expiration. "
                "The plain text key is only shown once - store it securely!",
)
async def generate_api_key(request: APIKeyCreate):
    """
    Generate a new API key.
    
    Returns both the plain text key (store this!) and the encrypted version
    that should be used in the X-API-Key header.
    """
    # Generate a new random API key
    plain_key = APIKeyEncryption.generate_api_key(prefix="sk")
    
    # Encrypt the key for use in headers
    encrypted_key = api_key_encryption.encrypt(plain_key)
    
    # Calculate expiration if specified
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # In production, store the key metadata in a database
    # For demo, we just add it to the in-memory validator
    api_key_validator.add_key(plain_key)
    
    return APIKeyResponse(
        name=request.name,
        key_plain=plain_key,
        key_encrypted=encrypted_key,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )


@router.post(
    "/keys/encrypt",
    response_model=dict,
    summary="Encrypt an API key",
    description="Encrypt an existing API key for use in the X-API-Key header.",
)
async def encrypt_api_key(plain_key: str):
    """Encrypt an API key."""
    encrypted = api_key_encryption.encrypt(plain_key)
    return {
        "plain_key": plain_key,
        "encrypted_key": encrypted,
    }


@router.post(
    "/keys/decrypt",
    response_model=APIKeyDecryptResponse,
    summary="Decrypt an API key",
    description="Decrypt an encrypted API key to verify its contents.",
    responses={400: {"model": ErrorResponse}},
)
async def decrypt_api_key(request: APIKeyDecrypt):
    """Decrypt an encrypted API key."""
    decrypted = api_key_encryption.decrypt(request.encrypted_key)
    
    if decrypted is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "decryption_failed",
                "message": "Failed to decrypt API key. It may be invalid or corrupted.",
            },
        )
    
    # Check if the decrypted key is valid
    is_valid, _ = api_key_validator.validate(decrypted, encrypted=False)
    
    return APIKeyDecryptResponse(
        decrypted_key=decrypted,
        is_valid=is_valid,
    )


@router.post(
    "/keys/validate",
    response_model=dict,
    summary="Validate an API key",
    description="Check if an API key is valid (can be encrypted or plain).",
)
async def validate_api_key(api_key: str, encrypted: bool = True):
    """
    Validate an API key.
    
    Args:
        api_key: The API key to validate
        encrypted: Whether the key is encrypted (default: True)
    """
    is_valid, decrypted_key = api_key_validator.validate(api_key, encrypted=encrypted)
    
    return {
        "is_valid": is_valid,
        "key_type": "encrypted" if encrypted else "plain",
    }


@router.delete(
    "/keys/revoke",
    response_model=SuccessResponse,
    summary="Revoke an API key",
    description="Revoke an API key so it can no longer be used.",
)
async def revoke_api_key(plain_key: str):
    """
    Revoke an API key.
    
    Note: This only removes the key from the in-memory store.
    In production, mark the key as revoked in the database.
    """
    api_key_validator.remove_key(plain_key)
    return SuccessResponse(message="API key revoked successfully")
