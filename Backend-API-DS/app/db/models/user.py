from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRoleEnum(str, enum.Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    STAFF = "staff"


if TYPE_CHECKING:
    from app.db.models.hospital import Hospital
    from app.db.models.auth_session import AuthSession
    from app.db.models.upload_session import UploadSession
    from app.db.models.job import Job
    from app.db.models.discharge_summary import DischargeSummary


class User(Base):
    """User table for doctors, nurses, and staff."""
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    hospital_id: Mapped[str] = mapped_column(
        ForeignKey("hospitals.hospital_id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRoleEnum.DOCTOR.value,
        nullable=False,
    )
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="users")
    auth_sessions: Mapped[List["AuthSession"]] = relationship(
        "AuthSession", back_populates="user", cascade="all, delete-orphan"
    )
    upload_sessions: Mapped[List["UploadSession"]] = relationship(
        "UploadSession", back_populates="user", cascade="all, delete-orphan"
    )
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="user")
    discharge_summaries: Mapped[List["DischargeSummary"]] = relationship(
        "DischargeSummary", back_populates="user"
    )
