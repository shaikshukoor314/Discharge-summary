from __future__ import annotations

from datetime import datetime
from typing import List
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class Template(Base):
    __tablename__ = "templates"

    template_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    template_type = Column(String, nullable=False)  # 'standard', 'detailed', 'brief'
    category = Column(String, nullable=False)  # 'General', 'Cardiology', 'Surgery', etc.
    sections = Column(JSON, nullable=False)  # Array of section descriptions
    estimated_time = Column(Integer, nullable=False)  # Minutes
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
