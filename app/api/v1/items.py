"""
Items CRUD API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.db.session import get_db
from app.models.all_models import Item
from app.schemas import (
    ErrorResponse,
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    PaginatedResponse,
    SuccessResponse,
)

router = APIRouter(prefix="/items", tags=["Items"])


@router.get(
    "",
    response_model=PaginatedResponse[ItemResponse],
    summary="List all items",
    description="Retrieve a paginated list of all items with optional filtering.",
)
async def list_items(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search in item name"),
    db: AsyncSession = Depends(get_db),
):
    """List all items with pagination and filtering."""
    # Build query
    query = select(Item)
    count_query = select(func.count()).select_from(Item)
    
    # Apply filters
    if is_active is not None:
        query = query.where(Item.is_active == is_active)
        count_query = count_query.where(Item.is_active == is_active)
        
    if search:
        search_filter = Item.name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Item.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse.create(
        items=[ItemResponse.model_validate(item.__dict__) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Get item by ID",
    responses={404: {"model": ErrorResponse}},
)
async def get_item(
    item_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a specific item by its ID."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Item with ID '{item_id}' not found"},
        )
    return ItemResponse.model_validate(item.__dict__)


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new item",
)
async def create_item(
    item: ItemCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new item."""
    db_item = Item(**item.model_dump())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return ItemResponse.model_validate(db_item.__dict__)


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update an item",
    responses={404: {"model": ErrorResponse}},
)
async def update_item(
    item_id: str, 
    item_update: ItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing item."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    db_item = result.scalar_one_or_none()
    
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Item with ID '{item_id}' not found"},
        )
    
    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
        
    await db.commit()
    await db.refresh(db_item)
    return ItemResponse.model_validate(db_item.__dict__)


@router.patch(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Partially update an item",
    responses={404: {"model": ErrorResponse}},
)
async def patch_item(
    item_id: str, 
    item: ItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Partially update an existing item."""
    return await update_item(item_id, item, db)


@router.delete(
    "/{item_id}",
    response_model=SuccessResponse,
    summary="Delete an item",
    responses={404: {"model": ErrorResponse}},
)
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an item by its ID."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Item with ID '{item_id}' not found"},
        )
        
    await db.delete(item)
    await db.commit()
    return SuccessResponse(message=f"Item '{item_id}' deleted successfully")


@router.delete(
    "",
    response_model=SuccessResponse,
    summary="Delete all items",
    description="Delete all items from the database. Use with caution!",
)
async def delete_all_items(db: AsyncSession = Depends(get_db)):
    """Delete all items."""
    result = await db.execute(delete(Item))
    await db.commit()
    return SuccessResponse(message=f"Deleted {result.rowcount} items")
