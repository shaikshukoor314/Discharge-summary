"""
Checkpoint routes for human verification tracking
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db_session
from app.db.models.job import Job
from app.schemas.checkpoint_schema import (
    CheckpointResponse,
    CheckpointUpdateRequest,
    CheckpointUpdateResponse,
    CheckpointState
)

from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/session-status-checkpoints", tags=["checkpoints"])

@router.get("/{job_id}", response_model=CheckpointResponse)
async def get_checkpoints(
    job_id: str,
    session: AsyncSession = Depends(get_db_session)
) -> CheckpointResponse:
    """Get checkpoint status for a job"""
    logger.info(f"🔍 Fetching checkpoints for job: {job_id}")
    
    result = await session.execute(
        select(Job).where(Job.job_id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        logger.error(f"❌ Job {job_id} not found in database")
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get checkpoints or use default
    raw_checkpoints = job.checkpoints
    if isinstance(raw_checkpoints, str):
        import json
        try:
            raw_checkpoints = json.loads(raw_checkpoints)
        except:
            raw_checkpoints = None

    checkpoints = raw_checkpoints or {
        "ocrCheckpoint": "pending",
        "dischargeMedicationsCheckpoint": "pending",
        "dischargeSummaryCheckpoint": "pending"
    }
    
    logger.info(f"✅ Checkpoints for {job_id}: {checkpoints}")
    
    checkpoint_state = CheckpointState(**checkpoints)
    all_completed = all(
        status == "completed" 
        for status in checkpoints.values()
    )
    
    return CheckpointResponse(
        job_id=job_id,
        checkpoints=checkpoint_state,
        all_completed=all_completed
    )

@router.patch("/{job_id}", response_model=CheckpointUpdateResponse)
async def update_checkpoint(
    job_id: str,
    update: CheckpointUpdateRequest,
    session: AsyncSession = Depends(get_db_session)
) -> CheckpointUpdateResponse:
    """Update a specific checkpoint status"""
    logger.info(f"📝 Updating checkpoint for {job_id}: {update.checkpoint_name} -> {update.status}")
    
    result = await session.execute(
        select(Job).where(Job.job_id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Initialize checkpoints if None
    if job.checkpoints is None:
        job.checkpoints = {
            "ocrCheckpoint": "pending",
            "dischargeMedicationsCheckpoint": "pending",
            "dischargeSummaryCheckpoint": "pending"
        }
    
    # Update checkpoint
    curr_checkpoints = job.checkpoints
    if isinstance(curr_checkpoints, str):
        import json
        try:
            curr_checkpoints = json.loads(curr_checkpoints)
        except:
            curr_checkpoints = {}
            
    checkpoints = dict(curr_checkpoints)  # Create mutable copy
    checkpoints[update.checkpoint_name] = update.status
    job.checkpoints = checkpoints
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "checkpoints")
    
    await session.commit()
    
    all_completed = all(
        status == "completed" 
        for status in checkpoints.values()
    )
    
    return CheckpointUpdateResponse(
        job_id=job_id,
        checkpoint_name=update.checkpoint_name,
        new_status=update.status,
        all_completed=all_completed
    )
