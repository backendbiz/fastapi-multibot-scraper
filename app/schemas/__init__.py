"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# Generic type for pagination
T = TypeVar("T")


# ============== Base Schemas ==============

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


# ============== Item Schemas ==============

class ItemBase(BaseModel):
    """Base schema for Item."""
    name: str = Field(..., min_length=1, max_length=255, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    price: float = Field(..., gt=0, description="Item price (must be positive)")
    quantity: int = Field(default=0, ge=0, description="Item quantity in stock")
    is_active: bool = Field(default=True, description="Whether item is active")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ItemCreate(ItemBase):
    """Schema for creating an Item."""
    pass


class ItemUpdate(BaseModel):
    """Schema for updating an Item (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    quantity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class ItemResponse(ItemBase, TimestampMixin):
    """Schema for Item response."""
    id: str = Field(..., description="Unique item identifier")


# ============== User Schemas ==============

class UserBase(BaseModel):
    """Base schema for User."""
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    full_name: Optional[str] = Field(None, max_length=100, description="Full name")
    is_active: bool = Field(default=True, description="Whether user is active")


class UserCreate(UserBase):
    """Schema for creating a User."""
    password: str = Field(..., min_length=8, description="User password")


class UserUpdate(BaseModel):
    """Schema for updating a User."""
    email: Optional[str] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class UserResponse(UserBase, TimestampMixin):
    """Schema for User response (excludes password)."""
    id: str = Field(..., description="Unique user identifier")


# ============== API Key Schemas ==============

class APIKeyCreate(BaseModel):
    """Schema for generating a new API key."""
    name: str = Field(..., min_length=1, max_length=100, description="Name/label for the API key")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")


class APIKeyResponse(BaseModel):
    """Schema for API key response."""
    name: str
    key_plain: str = Field(..., description="Plain text API key (only shown once)")
    key_encrypted: str = Field(..., description="Encrypted API key to use in X-API-Key header")
    created_at: datetime
    expires_at: Optional[datetime] = None


class APIKeyDecrypt(BaseModel):
    """Schema for decrypting an API key."""
    encrypted_key: str = Field(..., description="The encrypted API key to decrypt")


class APIKeyDecryptResponse(BaseModel):
    """Response for decrypted API key."""
    decrypted_key: str
    is_valid: bool


# ============== Pagination & Response Wrappers ==============

class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=10, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int
    
    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int):
        pages = (total + page_size - 1) // page_size
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
