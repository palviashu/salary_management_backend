from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.salary_contract import SalaryContract
    from app.models.payroll_record import PayrollRecord


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    country: Mapped[str] = mapped_column(String(100), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    all_contracts: Mapped[list[SalaryContract]] = relationship(
        "SalaryContract", back_populates="employee"
    )
    payroll_records: Mapped[list[PayrollRecord]] = relationship(
        "PayrollRecord", back_populates="employee"
    )

    __table_args__ = (
        Index("ix_employees_department_country", "department", "country"),
        Index("ix_employees_name", "last_name", "first_name"),
    )

    def __repr__(self) -> str:
        return f"<Employee {self.employee_id} {self.first_name} {self.last_name}>"
