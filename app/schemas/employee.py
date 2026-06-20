from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr


class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    department: str
    country: str


class EmployeeCreate(EmployeeBase):
    employee_id: str


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    department: str | None = None
    country: str | None = None
    is_active: bool | None = None


class SalaryContractBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_salary: Decimal
    allowances: Decimal
    deductions: Decimal
    net_salary: Decimal
    currency: str
    is_active: bool


class EmployeeRead(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: str
    is_active: bool
    created_at: datetime


class EmployeeWithContract(EmployeeRead):
    contract: SalaryContractBrief | None = None
