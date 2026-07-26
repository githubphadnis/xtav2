"""ORM models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Expense(Base):
    """A single expense row — original currency plus optional base amount."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spent_on: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_base: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    base_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    merchant: Mapped[str] = mapped_column(String(255), default="", index=True)
    category: Mapped[str] = mapped_column(String(128), default="", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(64), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="posted", index=True)
    receipt_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
