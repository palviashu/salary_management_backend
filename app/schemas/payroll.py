from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.payroll_batch import BatchStatus
from app.models.payroll_record import RecordStatus


class PayrollRunRequest(BaseModel):
    pay_period_start: date
    pay_period_end: date


class PayrollRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    base_salary_snapshot: Decimal
    allowances_snapshot: Decimal
    deductions_snapshot: Decimal
    net_salary_snapshot: Decimal
    status: RecordStatus
    paid_at: datetime | None


class BatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pay_period_start: date
    pay_period_end: date
    status: BatchStatus
    processed_at: datetime | None
    created_at: datetime
    total_records: int = 0
    total_net_payroll: Decimal = Decimal("0.00")


class BatchDetail(BatchSummary):
    records: list[PayrollRecordRead] = []
