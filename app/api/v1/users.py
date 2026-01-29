"""
Users CRUD API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.db.session import get_db
from app.models.all_models import User
from app.schemas import (
    ErrorResponse,
    PaginatedResponse,
    SuccessResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

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
    db: AsyncSession = Depends(get_db),
):
    """List all users with pagination and filtering."""
    # Build query
    query = select(User)
    count_query = select(func.count()).select_from(User)
    
    # Apply filters
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
        
    if search:
        search_filter = User.username.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(User.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    return PaginatedResponse.create(
        items=[UserResponse.model_validate(user.__dict__) for user in users],
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
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a specific user by their ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"User with ID '{user_id}' not found"},
        )
    return UserResponse.model_validate(user.__dict__)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user."""
    # In production, hash the password before storing
    user_data = user.model_dump(exclude={"password"})
    
    db_user = User(**user_data)
    # db_user.hashed_password = hash_password(user.password) # TODO: Implement hashing
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return UserResponse.model_validate(db_user.__dict__)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user",
    responses={404: {"model": ErrorResponse}},
)
async def update_user(
    user_id: str, 
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing user."""
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"User with ID '{user_id}' not found"},
        )
    
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    await db.commit()
    await db.refresh(db_user)
    return UserResponse.model_validate(db_user.__dict__)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Partially update a user",
    responses={404: {"model": ErrorResponse}},
)
async def patch_user(
    user_id: str, 
    user: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Partially update an existing user."""
    return await update_user(user_id, user, db)


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    summary="Delete a user",
    responses={404: {"model": ErrorResponse}},
)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a user by their ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
        
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"User with ID '{user_id}' not found"},
        )
    
    await db.delete(user)
    await db.commit()
    return SuccessResponse(message=f"User '{user_id}' deleted successfully")
