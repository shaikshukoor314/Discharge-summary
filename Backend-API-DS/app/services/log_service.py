from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.log_entry import LogEntry


class LogService:
    async def record(
        self,
        session: AsyncSession,
        level: str,
        message: str,
        job_id: str | None = None,
        document_id: str | None = None,
    ) -> None:
        entry = LogEntry(level=level, message=message, job_id=job_id, document_id=document_id)
        session.add(entry)
        await session.flush()


def get_log_service() -> LogService:
    return LogService()

