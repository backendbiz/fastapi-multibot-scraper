"""
In-memory database service for demo CRUD operations.
Replace with actual database (PostgreSQL, MongoDB, etc.) in production.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class InMemoryDB(Generic[T]):
    """
    Generic in-memory database for demo purposes.
    Thread-safe for basic operations.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._store: Dict[str, Dict[str, Any]] = {}
        self._counter = 0

    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new record."""
        record_id = self._generate_id()
        now = datetime.utcnow()
        
        record = {
            "id": record_id,
            **data,
            "created_at": now,
            "updated_at": None,
        }
        
        self._store[record_id] = record
        self._counter += 1
        logger.info(f"[{self.name}] Created record: {record_id}")
        return record

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Get a record by ID."""
        return self._store.get(record_id)

    def get_all(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Get all records with pagination and optional filters."""
        records = list(self._store.values())
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                records = [r for r in records if r.get(key) == value]
        
        # Sort by created_at descending
        records.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
        
        # Apply pagination
        return records[offset : offset + limit]

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters."""
        if not filters:
            return len(self._store)
        
        count = 0
        for record in self._store.values():
            match = all(record.get(k) == v for k, v in filters.items())
            if match:
                count += 1
        return count

    def update(self, record_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record."""
        if record_id not in self._store:
            return None
        
        record = self._store[record_id]
        
        # Update only provided fields
        for key, value in data.items():
            if value is not None:
                record[key] = value
        
        record["updated_at"] = datetime.utcnow()
        self._store[record_id] = record
        
        logger.info(f"[{self.name}] Updated record: {record_id}")
        return record

    def delete(self, record_id: str) -> bool:
        """Delete a record."""
        if record_id not in self._store:
            return False
        
        del self._store[record_id]
        logger.info(f"[{self.name}] Deleted record: {record_id}")
        return True

    def clear(self) -> int:
        """Clear all records. Returns count of deleted records."""
        count = len(self._store)
        self._store.clear()
        logger.info(f"[{self.name}] Cleared {count} records")
        return count

    def search(self, field: str, query: str) -> List[Dict[str, Any]]:
        """Simple text search on a field."""
        query_lower = query.lower()
        results = []
        
        for record in self._store.values():
            value = record.get(field, "")
            if isinstance(value, str) and query_lower in value.lower():
                results.append(record)
        
        return results


# Database instances for different entities
items_db = InMemoryDB(name="items")
users_db = InMemoryDB(name="users")


# Seed some initial data
def seed_initial_data():
    """Seed the database with initial demo data."""
    # Seed items
    demo_items = [
        {
            "name": "Laptop Pro X1",
            "description": "High-performance laptop for professionals",
            "price": 1299.99,
            "quantity": 50,
            "is_active": True,
            "metadata": {"brand": "TechCorp", "category": "electronics"},
        },
        {
            "name": "Wireless Mouse",
            "description": "Ergonomic wireless mouse with long battery life",
            "price": 49.99,
            "quantity": 200,
            "is_active": True,
            "metadata": {"brand": "PeriphCo", "category": "accessories"},
        },
        {
            "name": "USB-C Hub",
            "description": "7-in-1 USB-C hub with HDMI and card reader",
            "price": 79.99,
            "quantity": 75,
            "is_active": True,
            "metadata": {"brand": "ConnectPlus", "category": "accessories"},
        },
    ]
    
    for item in demo_items:
        items_db.create(item)
    
    # Seed users
    demo_users = [
        {
            "email": "admin@example.com",
            "username": "admin",
            "full_name": "Admin User",
            "is_active": True,
        },
        {
            "email": "user@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "is_active": True,
        },
    ]
    
    for user in demo_users:
        users_db.create(user)
    
    logger.info("Database seeded with initial data")


# Seed data on module import
seed_initial_data()
