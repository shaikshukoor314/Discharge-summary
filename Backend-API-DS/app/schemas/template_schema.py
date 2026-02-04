from __future__ import annotations

from typing import List
from pydantic import BaseModel


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    type: str
    category: str
    sections: List[str]
    estimatedTime: int

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]
