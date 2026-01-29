"""
Tests for the FastAPI Production Server.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import APIKeyEncryption, api_key_encryption
from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_header():
    """Create an authenticated header with dev API key."""
    return {"X-API-Key": "dev-key-123"}


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAPIKeyAuthentication:
    """Test API key authentication."""

    def test_missing_api_key(self, client):
        """Test request without API key is rejected."""
        response = client.get("/api/v1/items")
        assert response.status_code == 401
        assert "Missing" in response.json()["message"]

    def test_invalid_api_key(self, client):
        """Test request with invalid API key is rejected."""
        response = client.get(
            "/api/v1/items",
            headers={"X-API-Key": "invalid-key-12345"}
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["message"]

    def test_valid_api_key(self, client, auth_header):
        """Test request with valid API key succeeds."""
        response = client.get("/api/v1/items", headers=auth_header)
        assert response.status_code == 200


class TestAPIKeyEncryption:
    """Test API key encryption utilities."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        encryption = APIKeyEncryption()
        original = "sk_test_key_12345"
        
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == original
        assert encrypted != original

    def test_different_encryptions_produce_different_results(self):
        """Test that same plaintext produces different ciphertext (due to random nonce)."""
        encryption = APIKeyEncryption()
        original = "sk_test_key_12345"
        
        encrypted1 = encryption.encrypt(original)
        encrypted2 = encryption.encrypt(original)
        
        # Same plaintext should produce different ciphertext
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same value
        assert encryption.decrypt(encrypted1) == original
        assert encryption.decrypt(encrypted2) == original

    def test_decrypt_invalid_data_returns_none(self):
        """Test that decrypting invalid data returns None."""
        encryption = APIKeyEncryption()
        
        result = encryption.decrypt("invalid-base64-data!!!")
        assert result is None

    def test_generate_api_key(self):
        """Test API key generation."""
        key = APIKeyEncryption.generate_api_key(prefix="sk", length=32)
        
        assert key.startswith("sk_")
        assert len(key) > 32


class TestItemsCRUD:
    """Test Items CRUD endpoints."""

    def test_list_items(self, client, auth_header):
        """Test listing items."""
        response = client.get("/api/v1/items", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_create_item(self, client, auth_header):
        """Test creating an item."""
        item_data = {
            "name": "Test Item",
            "description": "A test item",
            "price": 99.99,
            "quantity": 10,
        }
        response = client.post("/api/v1/items", json=item_data, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Item"
        assert data["price"] == 99.99
        assert "id" in data

    def test_get_item(self, client, auth_header):
        """Test getting an item by ID."""
        # First create an item
        item_data = {"name": "Get Test", "price": 50.00}
        create_response = client.post("/api/v1/items", json=item_data, headers=auth_header)
        item_id = create_response.json()["id"]
        
        # Then get it
        response = client.get(f"/api/v1/items/{item_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == item_id

    def test_get_nonexistent_item(self, client, auth_header):
        """Test getting a nonexistent item returns 404."""
        response = client.get("/api/v1/items/nonexistent-id", headers=auth_header)
        assert response.status_code == 404

    def test_update_item(self, client, auth_header):
        """Test updating an item."""
        # Create item
        item_data = {"name": "Update Test", "price": 100.00}
        create_response = client.post("/api/v1/items", json=item_data, headers=auth_header)
        item_id = create_response.json()["id"]
        
        # Update it
        update_data = {"name": "Updated Name", "price": 150.00}
        response = client.put(f"/api/v1/items/{item_id}", json=update_data, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        assert response.json()["price"] == 150.00

    def test_delete_item(self, client, auth_header):
        """Test deleting an item."""
        # Create item
        item_data = {"name": "Delete Test", "price": 25.00}
        create_response = client.post("/api/v1/items", json=item_data, headers=auth_header)
        item_id = create_response.json()["id"]
        
        # Delete it
        response = client.delete(f"/api/v1/items/{item_id}", headers=auth_header)
        assert response.status_code == 200
        
        # Verify it's gone
        get_response = client.get(f"/api/v1/items/{item_id}", headers=auth_header)
        assert get_response.status_code == 404


class TestUsersCRUD:
    """Test Users CRUD endpoints."""

    def test_list_users(self, client, auth_header):
        """Test listing users."""
        response = client.get("/api/v1/users", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_create_user(self, client, auth_header):
        """Test creating a user."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser123",
            "full_name": "Test User",
            "password": "securepassword123",
        }
        response = client.post("/api/v1/users", json=user_data, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "id" in data
        # Password should not be in response
        assert "password" not in data


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_generate_api_key(self, client, auth_header):
        """Test generating a new API key."""
        response = client.post(
            "/api/v1/auth/keys/generate",
            json={"name": "test-key"},
            headers=auth_header,
        )
        assert response.status_code == 201
        data = response.json()
        assert "key_plain" in data
        assert "key_encrypted" in data
        assert data["name"] == "test-key"

    def test_decrypt_api_key(self, client, auth_header):
        """Test decrypting an API key."""
        # First generate a key
        gen_response = client.post(
            "/api/v1/auth/keys/generate",
            json={"name": "decrypt-test"},
            headers=auth_header,
        )
        encrypted_key = gen_response.json()["key_encrypted"]
        plain_key = gen_response.json()["key_plain"]
        
        # Decrypt it
        response = client.post(
            "/api/v1/auth/keys/decrypt",
            json={"encrypted_key": encrypted_key},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["decrypted_key"] == plain_key
