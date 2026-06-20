from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.payroll_batch import BatchStatus, PayrollBatch
from app.models.payroll_record import PayrollRecord, RecordStatus
from app.models.salary_contract import SalaryContract


class PayrollService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run_payroll(self, pay_period_start: date, pay_period_end: date) -> PayrollBatch:
        existing = self.db.execute(
            select(PayrollBatch).where(
                PayrollBatch.pay_period_start == pay_period_start,
                PayrollBatch.pay_period_end == pay_period_end,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Payroll batch for {pay_period_start}–{pay_period_end} already exists (id={existing.id})",
            )

        batch = PayrollBatch(
            pay_period_start=pay_period_start,
            pay_period_end=pay_period_end,
            status=BatchStatus.PROCESSING,
        )
        self.db.add(batch)
        self.db.flush()  # get batch.id without committing

        contracts = list(
            self.db.execute(
                select(SalaryContract)
                .where(SalaryContract.is_active == True)  # noqa: E712
                .join(SalaryContract.employee)
                .where(Employee.is_active == True)  # noqa: E712
            ).scalars().all()
        )

        if not contracts:
            raise HTTPException(
                status_code=422,
                detail="No active employees with active salary contracts found",
            )

        now = datetime.now(tz=timezone.utc)
        records_data = [
            {
                "batch_id": batch.id,
                "employee_id": c.employee_id,
                "base_salary_snapshot": c.base_salary,
                "allowances_snapshot": c.allowances,
                "deductions_snapshot": c.deductions,
                "net_salary_snapshot": c.net_salary,
                "status": RecordStatus.PENDING,
                "paid_at": None,
            }
            for c in contracts
        ]

        # Core INSERT with executemany — faster than ORM add_all for bulk
        chunk_size = 2000
        for i in range(0, len(records_data), chunk_size):
            self.db.execute(insert(PayrollRecord), records_data[i : i + chunk_size])

        batch.status = BatchStatus.DRAFT
        batch.processed_at = now
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def approve_batch(self, batch_id: int) -> PayrollBatch:
        batch = self._get_batch_or_404(batch_id)
        if batch.status != BatchStatus.DRAFT:
            raise HTTPException(
                status_code=422,
                detail=f"Only DRAFT batches can be approved; current status is {batch.status}",
            )
        now = datetime.now(tz=timezone.utc)
        self.db.execute(
            update(PayrollRecord)
            .where(PayrollRecord.batch_id == batch_id)
            .values(status=RecordStatus.SUCCESS, paid_at=now)
        )
        batch.status = BatchStatus.PAID
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def list_batches(self, page: int = 1, page_size: int = 20) -> tuple[list[PayrollBatch], int]:
        total = self.db.execute(select(func.count()).select_from(PayrollBatch)).scalar_one()
        batches = list(
            self.db.execute(
                select(PayrollBatch)
                .order_by(PayrollBatch.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return batches, total

    def get_batch_detail(
        self, batch_id: int, page: int = 1, page_size: int = 100
    ) -> tuple[PayrollBatch, list[PayrollRecord], int, Decimal]:
        batch = self._get_batch_or_404(batch_id)

        total_records = self.db.execute(
            select(func.count()).select_from(PayrollRecord).where(
                PayrollRecord.batch_id == batch_id
            )
        ).scalar_one()

        total_payroll = self.db.execute(
            select(func.sum(PayrollRecord.net_salary_snapshot)).where(
                PayrollRecord.batch_id == batch_id
            )
        ).scalar_one() or Decimal("0.00")

        records = list(
            self.db.execute(
                select(PayrollRecord)
                .where(PayrollRecord.batch_id == batch_id)
                .order_by(PayrollRecord.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )

        return batch, records, total_records, total_payroll

    def _get_batch_or_404(self, batch_id: int) -> PayrollBatch:
        batch = self.db.execute(
            select(PayrollBatch).where(PayrollBatch.id == batch_id)
        ).scalar_one_or_none()
        if batch is None:
            raise HTTPException(status_code=404, detail=f"Payroll batch {batch_id} not found")
        return batch
