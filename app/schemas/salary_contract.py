from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SalaryContractCreate(BaseModel):
    base_salary: Decimal
    allowances: Decimal = Decimal("0.00")
    deductions: Decimal = Decimal("0.00")
    effective_from: date
    currency: str = "USD"


class SalaryContractUpdate(BaseModel):
    base_salary: Decimal | None = None
    allowances: Decimal | None = None
    deductions: Decimal | None = None
    effective_from: date | None = None
    currency: str | None = None


class SalaryContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    base_salary: Decimal
    allowances: Decimal
    deductions: Decimal
    net_salary: Decimal
    effective_from: date
    currency: str
    is_active: bool
    created_at: datetime
