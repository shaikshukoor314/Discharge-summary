from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.template import Template
from app.db.session import get_db_session
from app.schemas.template_schema import TemplateResponse, TemplateListResponse
from app.utils.logger import get_logger

router = APIRouter(prefix="/templates", tags=["templates"])
logger = get_logger(__name__)


@router.get("", response_model=TemplateListResponse)
async def get_templates(session: AsyncSession = Depends(get_db_session)) -> TemplateListResponse:
    """
    Retrieve all active discharge summary templates.
    """
    result = await session.scalars(
        select(Template).where(Template.is_active == True).order_by(Template.category, Template.name)
    )
    templates = result.all()
    
    template_responses = [
        TemplateResponse(
            id=t.template_id,
            name=t.name,
            description=t.description,
            type=t.template_type,
            category=t.category,
            sections=t.sections,
            estimatedTime=t.estimated_time
        )
        for t in templates
    ]
    
    return TemplateListResponse(templates=template_responses)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, session: AsyncSession = Depends(get_db_session)) -> TemplateResponse:
    """
    Retrieve a specific template by ID.
    """
    template = await session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if not template.is_active:
        raise HTTPException(status_code=404, detail="Template is inactive")
    
    return TemplateResponse(
        id=template.template_id,
        name=template.name,
        description=template.description,
        type=template.template_type,
        category=template.category,
        sections=template.sections,
        estimatedTime=template.estimated_time
    )
