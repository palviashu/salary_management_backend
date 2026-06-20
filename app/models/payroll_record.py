from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.payroll_batch import PayrollBatch


class RecordStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("payroll_batches.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))

    # Salary snapshot at the time payroll ran — immutable audit trail
    base_salary_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    allowances_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    deductions_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    net_salary_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus, name="recordstatus"), default=RecordStatus.PENDING
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[PayrollBatch] = relationship("PayrollBatch", back_populates="records")
    employee: Mapped[Employee] = relationship("Employee", back_populates="payroll_records")

    __table_args__ = (
        Index("ix_records_batch_status", "batch_id", "status"),
        Index("ix_records_employee", "employee_id"),
    )

    def __repr__(self) -> str:
        return f"<PayrollRecord batch={self.batch_id} emp={self.employee_id} [{self.status}]>"
