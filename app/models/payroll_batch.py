from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.payroll_record import PayrollRecord


class BatchStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"


class PayrollBatch(Base):
    __tablename__ = "payroll_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    pay_period_start: Mapped[date] = mapped_column(Date)
    pay_period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, name="batchstatus"), default=BatchStatus.DRAFT
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    records: Mapped[list[PayrollRecord]] = relationship(
        "PayrollRecord", back_populates="batch", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("pay_period_start", "pay_period_end", name="uq_batch_period"),
        Index("ix_batches_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<PayrollBatch {self.pay_period_start}→{self.pay_period_end} [{self.status}]>"
