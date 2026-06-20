"""Unit tests for PayrollService — core business logic."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.payroll_batch import BatchStatus
from app.models.payroll_record import RecordStatus
from app.models.salary_contract import SalaryContract
from app.services.payroll_service import PayrollService


def _seed_employee(db: Session, suffix: str, base: Decimal = Decimal("80000"), active: bool = True) -> tuple[Employee, SalaryContract]:
    emp = Employee(
        employee_id=f"PAY{suffix}",
        first_name="Test",
        last_name=f"User{suffix}",
        email=f"paytest.{suffix}@acme.com",
        department="Engineering",
        country="United States",
        is_active=active,
    )
    db.add(emp)
    db.flush()

    contract = SalaryContract(
        employee_id=emp.id,
        base_salary=base,
        allowances=Decimal("5000.00"),
        deductions=Decimal("8000.00"),
        effective_from=date(2024, 1, 1),
        currency="USD",
        is_active=True,
    )
    db.add(contract)
    db.flush()
    return emp, contract


class TestPayrollService:
    def test_run_payroll_creates_batch_and_records(self, db: Session):
        emp, contract = _seed_employee(db, "RUN01")
        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 1, 1), date(2026, 1, 31))

        assert batch.id is not None
        assert batch.status == BatchStatus.DRAFT
        assert batch.processed_at is not None

        # Verify a record was created for our employee
        from sqlalchemy import select
        from app.models.payroll_record import PayrollRecord
        records = db.execute(
            select(PayrollRecord).where(PayrollRecord.batch_id == batch.id)
        ).scalars().all()
        assert len(records) >= 1
        our_record = next((r for r in records if r.employee_id == emp.id), None)
        assert our_record is not None

    def test_run_payroll_snapshots_correct_salary_values(self, db: Session):
        base = Decimal("100000.00")
        allowances = Decimal("5000.00")
        deductions = Decimal("8000.00")
        expected_net = base + allowances - deductions

        emp, contract = _seed_employee(db, "SNAP01", base=base)
        contract.allowances = allowances
        contract.deductions = deductions
        db.flush()

        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 2, 1), date(2026, 2, 28))

        from sqlalchemy import select
        from app.models.payroll_record import PayrollRecord
        record = db.execute(
            select(PayrollRecord).where(
                PayrollRecord.batch_id == batch.id,
                PayrollRecord.employee_id == emp.id,
            )
        ).scalar_one()

        assert record.base_salary_snapshot == base
        assert record.allowances_snapshot == allowances
        assert record.deductions_snapshot == deductions
        assert record.net_salary_snapshot == expected_net

    def test_run_payroll_duplicate_period_raises_409(self, db: Session):
        _seed_employee(db, "DUP01")
        svc = PayrollService(db)
        svc.run_payroll(date(2026, 3, 1), date(2026, 3, 31))

        with pytest.raises(HTTPException) as exc:
            svc.run_payroll(date(2026, 3, 1), date(2026, 3, 31))
        assert exc.value.status_code == 409

    def test_run_payroll_skips_inactive_employees(self, db: Session):
        active_emp, _ = _seed_employee(db, "ACT01", active=True)
        inactive_emp, _ = _seed_employee(db, "INACT01", active=False)

        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 4, 1), date(2026, 4, 30))

        from sqlalchemy import select
        from app.models.payroll_record import PayrollRecord
        record_emp_ids = {
            r.employee_id for r in db.execute(
                select(PayrollRecord).where(PayrollRecord.batch_id == batch.id)
            ).scalars().all()
        }
        assert active_emp.id in record_emp_ids
        assert inactive_emp.id not in record_emp_ids

    def test_run_payroll_records_are_pending_initially(self, db: Session):
        _seed_employee(db, "PEND01")
        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 5, 1), date(2026, 5, 31))

        from sqlalchemy import select
        from app.models.payroll_record import PayrollRecord
        records = db.execute(
            select(PayrollRecord).where(PayrollRecord.batch_id == batch.id)
        ).scalars().all()
        assert all(r.status == RecordStatus.PENDING for r in records)

    def test_approve_batch_transitions_to_paid(self, db: Session):
        _seed_employee(db, "APPR01")
        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 6, 1), date(2026, 6, 30))
        assert batch.status == BatchStatus.DRAFT

        approved = svc.approve_batch(batch.id)
        assert approved.status == BatchStatus.PAID

    def test_approve_batch_marks_records_success(self, db: Session):
        _seed_employee(db, "APPR02")
        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 7, 1), date(2026, 7, 31))
        svc.approve_batch(batch.id)

        from sqlalchemy import select
        from app.models.payroll_record import PayrollRecord
        records = db.execute(
            select(PayrollRecord).where(PayrollRecord.batch_id == batch.id)
        ).scalars().all()
        assert all(r.status == RecordStatus.SUCCESS for r in records)
        assert all(r.paid_at is not None for r in records)

    def test_approve_batch_wrong_status_raises_422(self, db: Session):
        _seed_employee(db, "APPR03")
        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 8, 1), date(2026, 8, 31))
        svc.approve_batch(batch.id)  # now PAID

        with pytest.raises(HTTPException) as exc:
            svc.approve_batch(batch.id)  # can't approve twice
        assert exc.value.status_code == 422

    def test_get_batch_detail_returns_correct_totals(self, db: Session):
        base = Decimal("90000.00")
        _seed_employee(db, "TOT01", base=base)
        _seed_employee(db, "TOT02", base=base)
        svc = PayrollService(db)
        batch = svc.run_payroll(date(2026, 9, 1), date(2026, 9, 30))

        _, records, total_records, total_payroll = svc.get_batch_detail(batch.id)
        assert total_records >= 2
        assert total_payroll > Decimal("0")
