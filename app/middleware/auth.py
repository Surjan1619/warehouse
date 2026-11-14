from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from app.core.config import settings

class AuthMiddleware(BaseHTTPMiddleware):
    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        # An HTTPException raised inside a middleware is not handled by FastAPI
        # and turns into a 500, so the response is built explicitly.
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )

    async def dispatch(self, request: Request, call_next):
        # Let CORS preflight requests through: browsers send them without a token
        if request.method == "OPTIONS":
            return await call_next(request)

        # Allow public endpoints
        if request.url.path in ["/auth/login", "/docs", "/openapi.json", "/", "/favicon.svg"]:
            return await call_next(request)

        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._unauthorized("Missing or invalid token")
        
        token = auth_header.split(" ")[1]
        try:
            # Decode and verify token
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
            request.state.user_id = payload.get("sub")
        except JWTError:
            return self._unauthorized("Invalid or expired token")

        return await call_next(request)
