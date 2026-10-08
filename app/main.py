from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine, get_db
from app.core.config import settings

app = FastAPI(title=settings.app_name)


app.get("/health/db")
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

    except Exception as exc:
        return {
            "database": "error",
            "detail": str(exc),
        }
        
         
