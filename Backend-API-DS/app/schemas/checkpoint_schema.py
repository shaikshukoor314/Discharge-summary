"""
Checkpoint schemas for human verification tracking
"""
from pydantic import BaseModel, Field
from typing import Literal

CheckpointStatus = Literal["pending", "completed"]

class CheckpointState(BaseModel):
    """Individual checkpoint status"""
    ocrCheckpoint: CheckpointStatus = "pending"
    dischargeMedicationsCheckpoint: CheckpointStatus = "pending"
    dischargeSummaryCheckpoint: CheckpointStatus = "pending"

class CheckpointResponse(BaseModel):
    """Response for GET /session-status-checkpoints/{job_id}"""
    job_id: str
    checkpoints: CheckpointState
    all_completed: bool = Field(
        description="True if all checkpoints are completed"
    )

class CheckpointUpdateRequest(BaseModel):
    """Request to update specific checkpoint"""
    checkpoint_name: Literal[
        "ocrCheckpoint",
        "dischargeMedicationsCheckpoint", 
        "dischargeSummaryCheckpoint"
    ]
    status: CheckpointStatus

class CheckpointUpdateResponse(BaseModel):
    """Response after updating checkpoint"""
    job_id: str
    checkpoint_name: str
    new_status: CheckpointStatus
    all_completed: bool
