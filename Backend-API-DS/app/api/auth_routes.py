from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.db.models.user import User
from app.middleware.auth_middleware import get_current_user
from app.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
    ChangePasswordRequest,
)
from app.services.auth_service import get_auth_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = get_logger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    """
    Authenticate user and return access token.
    """
    auth_service = get_auth_service()
    
    # Get client info for session tracking
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    result = await auth_service.login(
        session=session,
        email=login_data.email,
        password=login_data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return result


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Logout current user and invalidate token.
    """
    auth_service = get_auth_service()
    
    # Get token from Authorization header
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    await auth_service.logout(session, token)
    
    return {"message": "Successfully logged out"}


@router.post("/logout-all", status_code=status.HTTP_200_OK)
async def logout_all(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Logout from all devices/sessions.
    """
    auth_service = get_auth_service()
    count = await auth_service.logout_all(session, current_user.user_id)
    
    return {"message": f"Successfully logged out from {count} session(s)"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user information.
    """
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        department=current_user.department,
        hospital_id=current_user.hospital_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    register_data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Register a new user.
    Note: In production, this should be admin-only or have additional validation.
    """
    auth_service = get_auth_service()
    
    user = await auth_service.register_user(
        session=session,
        email=register_data.email,
        password=register_data.password,
        full_name=register_data.full_name,
        hospital_id=register_data.hospital_id,
        role=register_data.role,
        department=register_data.department,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Email may already exist or hospital not found.",
        )

    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        department=user.department,
        hospital_id=user.hospital_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Change current user's password.
    """
    auth_service = get_auth_service()
    
    success = await auth_service.change_password(
        session=session,
        user_id=current_user.user_id,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password",
        )

    return {"message": "Password changed successfully. Please login again."}
