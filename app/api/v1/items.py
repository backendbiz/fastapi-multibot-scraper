"""
Items CRUD API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import (
    ErrorResponse,
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    PaginatedResponse,
    SuccessResponse,
)
from app.services.database import items_db

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
):
    """List all items with pagination and filtering."""
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active

    # If search is provided, use search function
    if search:
        items = items_db.search("name", search)
        if is_active is not None:
            items = [i for i in items if i.get("is_active") == is_active]
        total = len(items)
        offset = (page - 1) * page_size
        items = items[offset : offset + page_size]
    else:
        total = items_db.count(filters if filters else None)
        offset = (page - 1) * page_size
        items = items_db.get_all(offset=offset, limit=page_size, filters=filters if filters else None)

    return PaginatedResponse.create(
        items=[ItemResponse(**item) for item in items],
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
async def get_item(item_id: str):
    """Retrieve a specific item by its ID."""
    item = items_db.get(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Item with ID '{item_id}' not found"},
        )
    return ItemResponse(**item)


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new item",
)
async def create_item(item: ItemCreate):
    """Create a new item."""
    item_data = item.model_dump()
    created_item = items_db.create(item_data)
    return ItemResponse(**created_item)


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update an item",
    responses={404: {"model": ErrorResponse}},
)
async def update_item(item_id: str, item: ItemUpdate):
    """Update an existing item."""
    existing = items_db.get(item_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Item with ID '{item_id}' not found"},
        )
    
    update_data = item.model_dump(exclude_unset=True)
    updated_item = items_db.update(item_id, update_data)
    return ItemResponse(**updated_item)


@router.patch(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Partially update an item",
    responses={404: {"model": ErrorResponse}},
)
async def patch_item(item_id: str, item: ItemUpdate):
    """Partially update an existing item."""
    return await update_item(item_id, item)


@router.delete(
    "/{item_id}",
    response_model=SuccessResponse,
    summary="Delete an item",
    responses={404: {"model": ErrorResponse}},
)
async def delete_item(item_id: str):
    """Delete an item by its ID."""
    if not items_db.delete(item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Item with ID '{item_id}' not found"},
        )
    return SuccessResponse(message=f"Item '{item_id}' deleted successfully")


@router.delete(
    "",
    response_model=SuccessResponse,
    summary="Delete all items",
    description="Delete all items from the database. Use with caution!",
)
async def delete_all_items():
    """Delete all items."""
    count = items_db.clear()
    return SuccessResponse(message=f"Deleted {count} items")
