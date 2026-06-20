from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.employee import Employee


class SalaryContract(TimestampMixin, Base):
    __tablename__ = "salary_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    allowances: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    effective_from: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    employee: Mapped[Employee] = relationship(
        "Employee", back_populates="all_contracts", foreign_keys=[employee_id]
    )

    @property
    def net_salary(self) -> Decimal:
        return self.base_salary + self.allowances - self.deductions

    __table_args__ = (
        Index("ix_contracts_employee_active", "employee_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<SalaryContract emp_id={self.employee_id} net={self.net_salary}>"
