from fastapi import Depends, FastAPI
from app.db.session import engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings

from app.db.session import get_db
app = FastAPI(title=settings.app_name)


@app.get("/health/db")
async def check_database():
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT 1")
            )
            value = result.scalar_one()

        return {
            "database": "connected",
            "query_result": value,
        }

    except SQLAlchemyError as exc:
        return {
            "database": "error",
            "detail": str(exc),
        }



@app.get("/health/db/session")
async def check_database(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("SELECT 1"))

    return {
        "database": "connected",
        "query_result": result.scalar_one(),
    }