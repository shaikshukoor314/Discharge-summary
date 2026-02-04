from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    priority: Optional[int] = 5


class FileStageStatus(BaseModel):
    file: str
    ocr: str
    spellcheck: str
    deid: str


class ProcessResponse(BaseModel):
    jobId: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    overall_progress: str | None = None
    files: List[FileStageStatus] = Field(default_factory=list)
    message: str | None = None

