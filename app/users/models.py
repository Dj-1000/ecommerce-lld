from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)

    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"