from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.db.models.user import User
from app.services.auth_service import get_auth_service

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Dependency to get the current authenticated user.
    Raises HTTPException if not authenticated.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = get_auth_service()
    user = await auth_service.validate_session(session, credentials.credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    Dependency to get the current user if authenticated.
    Returns None if not authenticated (doesn't raise exception).
    """
    if not credentials:
        return None

    auth_service = get_auth_service()
    return await auth_service.validate_session(session, credentials.credentials)


def require_role(*allowed_roles: str):
    """
    Dependency factory to require specific roles.
    Usage: Depends(require_role("admin", "doctor"))
    """
    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}",
            )
        return user
    
    return role_checker


# Pre-configured role dependencies
require_admin = require_role("admin")
require_doctor = require_role("admin", "doctor")
require_staff = require_role("admin", "doctor", "nurse", "staff")
