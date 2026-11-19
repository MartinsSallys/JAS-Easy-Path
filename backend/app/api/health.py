from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas import HealthResponse

router = APIRouter(prefix="", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy")


@router.get("/health/ready")
async def readiness_check(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": "disconnected", "error": str(e)}