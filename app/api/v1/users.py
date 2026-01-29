"""
Users CRUD API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import (
    ErrorResponse,
    PaginatedResponse,
    SuccessResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.database import users_db

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="List all users",
    description="Retrieve a paginated list of all users with optional filtering.",
)
async def list_users(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search in username"),
):
    """List all users with pagination and filtering."""
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active

    # If search is provided, use search function
    if search:
        users = users_db.search("username", search)
        if is_active is not None:
            users = [u for u in users if u.get("is_active") == is_active]
        total = len(users)
        offset = (page - 1) * page_size
        users = users[offset : offset + page_size]
    else:
        total = users_db.count(filters if filters else None)
        offset = (page - 1) * page_size
        users = users_db.get_all(offset=offset, limit=page_size, filters=filters if filters else None)

    return PaginatedResponse.create(
        items=[UserResponse(**user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    responses={404: {"model": ErrorResponse}},
)
async def get_user(user_id: str):
    """Retrieve a specific user by their ID."""
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"User with ID '{user_id}' not found"},
        )
    return UserResponse(**user)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(user: UserCreate):
    """Create a new user."""
    # In production, hash the password before storing
    user_data = user.model_dump(exclude={"password"})
    # user_data["password_hash"] = hash_password(user.password)
    
    created_user = users_db.create(user_data)
    return UserResponse(**created_user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user",
    responses={404: {"model": ErrorResponse}},
)
async def update_user(user_id: str, user: UserUpdate):
    """Update an existing user."""
    existing = users_db.get(user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"User with ID '{user_id}' not found"},
        )
    
    update_data = user.model_dump(exclude_unset=True)
    updated_user = users_db.update(user_id, update_data)
    return UserResponse(**updated_user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Partially update a user",
    responses={404: {"model": ErrorResponse}},
)
async def patch_user(user_id: str, user: UserUpdate):
    """Partially update an existing user."""
    return await update_user(user_id, user)


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    summary="Delete a user",
    responses={404: {"model": ErrorResponse}},
)
async def delete_user(user_id: str):
    """Delete a user by their ID."""
    if not users_db.delete(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"User with ID '{user_id}' not found"},
        )
    return SuccessResponse(message=f"User '{user_id}' deleted successfully")
