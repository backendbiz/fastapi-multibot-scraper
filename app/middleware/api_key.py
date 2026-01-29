"""
API Key Authentication Middleware.
Validates encrypted API keys from request headers.
"""
import logging
import time
from typing import Callable, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.security import api_key_validator

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.
    
    Validates the X-API-Key header (or configured header name) against
    a list of valid encrypted API keys.
    """

    # Paths that don't require authentication
    EXEMPT_PATHS: List[str] = [
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    ]

    def __init__(self, app: Callable, exempt_paths: List[str] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or self.EXEMPT_PATHS
        self.header_name = settings.API_KEY_HEADER_NAME

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and validate API key if required."""
        start_time = time.time()
        
        # Check if path is exempt from authentication
        path = request.url.path
        if self._is_exempt(path):
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get(self.header_name)
        
        if not api_key:
            logger.warning(f"Missing API key for request to {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": f"Missing {self.header_name} header",
                },
            )

        # Validate the API key (try encrypted first, then plain in dev mode)
        is_valid, decrypted_key = api_key_validator.validate(api_key, encrypted=True)
        
        if not is_valid:
            logger.warning(f"Invalid API key for request to {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid API key",
                },
            )

        # Store the decrypted key in request state for later use
        request.state.api_key = decrypted_key

        # Process the request
        response = await call_next(request)

        # Add timing header
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        return response

    def _is_exempt(self, path: str) -> bool:
        """Check if the path is exempt from API key validation."""
        # Exact match
        if path in self.exempt_paths:
            return True
        
        # Prefix match for docs
        for exempt in self.exempt_paths:
            if path.startswith(exempt) and exempt != "/":
                return True
                
        return False
