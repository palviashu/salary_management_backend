from decimal import Decimal

from pydantic import BaseModel

from app.models.payroll_batch import BatchStatus


class DepartmentSummary(BaseModel):
    department: str
    employee_count: int
    total_net_salary: Decimal
    avg_net_salary: Decimal


class CountrySummary(BaseModel):
    country: str
    employee_count: int
    total_net_salary: Decimal
    avg_net_salary: Decimal


class SalaryBucket(BaseModel):
    bucket_label: str
    count: int
    min_salary: Decimal
    max_salary: Decimal


class DashboardSummary(BaseModel):
    total_active_employees: int
    total_inactive_employees: int
    total_monthly_payroll: Decimal
    avg_salary: Decimal
    latest_batch_status: BatchStatus | None
    latest_batch_id: int | None
    department_breakdown: list[DepartmentSummary]
    country_breakdown: list[CountrySummary]
