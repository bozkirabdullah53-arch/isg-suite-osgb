"""Scoped visitor registration and expiring QR passes."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class VisitorPass(Base):
    __tablename__ = "visitor_passes"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    organization: Mapped[str | None] = mapped_column(String(220), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    purpose: Mapped[str] = mapped_column(String(500))
    valid_from: Mapped[datetime] = mapped_column(DateTime, index=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="issued", index=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
