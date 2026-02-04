from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.db.models.user import User
from app.db.models.auth_session import AuthSession
from app.db.models.hospital import Hospital
from app.schemas.auth_schema import LoginResponse, TokenPayload, UserResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AuthService:
    """Authentication service for user login, logout, and token management."""

    def __init__(self) -> None:
        self.secret_key = settings.jwt_secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.jwt_expire_minutes

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt, password_hash = stored_hash.split(":")
            new_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return secrets.compare_digest(new_hash, password_hash)
        except ValueError:
            return False

    def create_access_token(self, user: User) -> tuple[str, datetime]:
        """Create JWT access token."""
        expires_at = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": user.user_id,
            "hospital_id": user.hospital_id,
            "role": user.role,
            "exp": expires_at,
            "iat": datetime.utcnow(),
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, expires_at

    def decode_token(self, token: str) -> Optional[TokenPayload]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenPayload(
                sub=payload["sub"],
                hospital_id=payload["hospital_id"],
                role=payload["role"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
            )
        except jwt.ExpiredSignatureError:
            logger.warning("auth.token_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("auth.invalid_token", error=str(e))
            return None

    async def login(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[LoginResponse]:
        """Authenticate user and create session."""
        # Find user by email
        user = await session.scalar(
            select(User).where(User.email == email, User.is_active == True)
        )
        
        if not user:
            logger.warning("auth.login_failed", reason="user_not_found", email=email)
            return None

        # Verify password
        if not self.verify_password(password, user.password_hash):
            logger.warning("auth.login_failed", reason="invalid_password", email=email)
            return None

        # Create access token
        token, expires_at = self.create_access_token(user)

        # Store session in database
        auth_session = AuthSession(
            user_id=user.user_id,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(auth_session)
        await session.commit()

        logger.info("auth.login_success", user_id=user.user_id, email=email)

        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user_id=user.user_id,
            hospital_id=user.hospital_id,
            full_name=user.full_name,
            role=user.role,
            expires_at=expires_at,
        )

    async def logout(self, session: AsyncSession, token: str) -> bool:
        """Invalidate user session."""
        result = await session.execute(
            delete(AuthSession).where(AuthSession.token == token)
        )
        await session.commit()
        
        if result.rowcount > 0:
            logger.info("auth.logout_success")
            return True
        return False

    async def logout_all(self, session: AsyncSession, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        result = await session.execute(
            delete(AuthSession).where(AuthSession.user_id == user_id)
        )
        await session.commit()
        
        logger.info("auth.logout_all", user_id=user_id, sessions_invalidated=result.rowcount)
        return result.rowcount

    async def validate_session(
        self,
        session: AsyncSession,
        token: str,
    ) -> Optional[User]:
        """Validate token and return user if valid."""
        # Decode token
        payload = self.decode_token(token)
        if not payload:
            return None

        # Check if session exists and is not expired
        auth_session = await session.scalar(
            select(AuthSession).where(
                AuthSession.token == token,
                AuthSession.expires_at > datetime.utcnow(),
            )
        )
        
        if not auth_session:
            logger.warning("auth.session_not_found_or_expired")
            return None

        # Get user
        user = await session.get(User, payload.sub)
        if not user or not user.is_active:
            return None

        return user

    async def get_user_by_id(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> Optional[UserResponse]:
        """Get user by ID."""
        user = await session.get(User, user_id)
        if not user:
            return None

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

    async def register_user(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        full_name: str,
        hospital_id: str,
        role: str = "doctor",
        department: Optional[str] = None,
    ) -> Optional[User]:
        """Register a new user."""
        # Check if email already exists
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            logger.warning("auth.registration_failed", reason="email_exists", email=email)
            return None

        # Check if hospital exists
        hospital = await session.get(Hospital, hospital_id)
        if not hospital:
            logger.warning("auth.registration_failed", reason="hospital_not_found", hospital_id=hospital_id)
            return None

        # Create user
        user = User(
            email=email,
            password_hash=self.hash_password(password),
            full_name=full_name,
            hospital_id=hospital_id,
            role=role,
            department=department,
        )
        session.add(user)
        await session.commit()

        logger.info("auth.registration_success", user_id=user.user_id, email=email)
        return user

    async def change_password(
        self,
        session: AsyncSession,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password."""
        user = await session.get(User, user_id)
        if not user:
            return False

        if not self.verify_password(current_password, user.password_hash):
            logger.warning("auth.change_password_failed", reason="invalid_current_password", user_id=user_id)
            return False

        user.password_hash = self.hash_password(new_password)
        await session.commit()

        # Invalidate all sessions (force re-login)
        await self.logout_all(session, user_id)

        logger.info("auth.password_changed", user_id=user_id)
        return True


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
