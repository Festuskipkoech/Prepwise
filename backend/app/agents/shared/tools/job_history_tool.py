import logging
import uuid

from langchain_core.tools import tool
from sqlalchemy import select
 
from app.db.session import AsyncSessionFactory
from app.db.models.jobs import Job
 
logger = logging.getLogger(__name__)

def build_job_history_tool(user_id: str):
    _user_uuid = uuid.UUID(user_id)
    @tool
    async def get_recent_job_searches(limit: int = 5) -> str:
        """Retrieve the user's most recently saved or searched jobs.
        Use this to understand what roles the user is targeting, which
        companies they are interested in, and the status of their search.
        Limit must be between 1 and 20."""
        limit = max(1, min(limit, 20))

        try:
            async with AsyncSessionFactory() as db:
                result = await db.execute(
                    select(Job)
                    .where(Job.user_id == _user_uuid)
                    .order_by(Job.created_at.desc())
                    .limit(limit)
                )
                jobs = result.scalars().all()

            if not jobs:
                return "No saved jobs found."

            lines = []
            for job in jobs:
                parts = [f"{job.title} at {job.company or 'Unknown company'}"]
                if job.status:
                    parts.append(f"status: {job.status}")
                if job.applied_date:
                    parts.append(f"applied: {job.applied_date}")
                lines.append(" | ".join(parts))
        
        except Exception:

            logger.exception(
                "get_recent_job_searches failed for user %s", user_id
            )
            return "Job history could not be retrieved at this time."
    
    return get_recent_job_searches
                

