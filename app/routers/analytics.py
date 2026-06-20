from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.employee import Employee
from app.models.payroll_batch import BatchStatus, PayrollBatch
from app.models.payroll_record import PayrollRecord
from app.models.salary_contract import SalaryContract
from app.schemas.analytics import (
    CountrySummary,
    DashboardSummary,
    DepartmentSummary,
    SalaryBucket,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(db: Session = Depends(get_db)):
    counts = db.execute(
        select(Employee.is_active, func.count().label("cnt")).group_by(Employee.is_active)
    ).all()
    active_count = next((r.cnt for r in counts if r.is_active), 0)
    inactive_count = next((r.cnt for r in counts if not r.is_active), 0)

    salary_agg = db.execute(
        select(
            func.sum(
                SalaryContract.base_salary + SalaryContract.allowances - SalaryContract.deductions
            ).label("total"),
            func.avg(
                SalaryContract.base_salary + SalaryContract.allowances - SalaryContract.deductions
            ).label("avg"),
        )
        .join(SalaryContract.employee)
        .where(SalaryContract.is_active == True)  # noqa: E712
        .where(Employee.is_active == True)  # noqa: E712
    ).one()
    total_payroll = salary_agg.total or Decimal("0.00")
    avg_salary = salary_agg.avg or Decimal("0.00")

    latest_batch = db.execute(
        select(PayrollBatch).order_by(PayrollBatch.created_at.desc()).limit(1)
    ).scalar_one_or_none()

    return DashboardSummary(
        total_active_employees=active_count,
        total_inactive_employees=inactive_count,
        total_monthly_payroll=total_payroll,
        avg_salary=avg_salary,
        latest_batch_status=latest_batch.status if latest_batch else None,
        latest_batch_id=latest_batch.id if latest_batch else None,
        department_breakdown=_department_breakdown(db),
        country_breakdown=_country_breakdown(db),
    )


@router.get("/by-department", response_model=list[DepartmentSummary])
def by_department(db: Session = Depends(get_db)):
    return _department_breakdown(db)


@router.get("/by-country", response_model=list[CountrySummary])
def by_country(db: Session = Depends(get_db)):
    return _country_breakdown(db)


@router.get("/salary-distribution", response_model=list[SalaryBucket])
def salary_distribution(db: Session = Depends(get_db)):
    net = SalaryContract.base_salary + SalaryContract.allowances - SalaryContract.deductions
    bucket_expr = case(
        (net < 30_000, "< 30k"),
        (net < 60_000, "30k–60k"),
        (net < 90_000, "60k–90k"),
        (net < 120_000, "90k–120k"),
        (net < 150_000, "120k–150k"),
        (net < 200_000, "150k–200k"),
        else_="> 200k",
    )
    order_expr = case(
        (net < 30_000, 0),
        (net < 60_000, 1),
        (net < 90_000, 2),
        (net < 120_000, 3),
        (net < 150_000, 4),
        (net < 200_000, 5),
        else_=6,
    )
    rows = db.execute(
        select(
            bucket_expr.label("label"),
            func.count().label("cnt"),
            func.min(net).label("min_sal"),
            func.max(net).label("max_sal"),
        )
        .join(SalaryContract.employee)
        .where(SalaryContract.is_active == True)  # noqa: E712
        .where(Employee.is_active == True)  # noqa: E712
        .group_by(bucket_expr, order_expr)
        .order_by(order_expr)
    ).all()

    return [
        SalaryBucket(
            bucket_label=r.label,
            count=r.cnt,
            min_salary=r.min_sal or Decimal("0"),
            max_salary=r.max_sal or Decimal("0"),
        )
        for r in rows
    ]


def _department_breakdown(db: Session) -> list[DepartmentSummary]:
    net = SalaryContract.base_salary + SalaryContract.allowances - SalaryContract.deductions
    rows = db.execute(
        select(
            Employee.department,
            func.count(Employee.id).label("emp_count"),
            func.sum(net).label("total"),
            func.avg(net).label("avg"),
        )
        .join(SalaryContract, SalaryContract.employee_id == Employee.id)
        .where(SalaryContract.is_active == True)  # noqa: E712
        .where(Employee.is_active == True)  # noqa: E712
        .group_by(Employee.department)
        .order_by(func.sum(net).desc())
    ).all()
    return [
        DepartmentSummary(
            department=r.department,
            employee_count=r.emp_count,
            total_net_salary=r.total or Decimal("0"),
            avg_net_salary=r.avg or Decimal("0"),
        )
        for r in rows
    ]


def _country_breakdown(db: Session) -> list[CountrySummary]:
    net = SalaryContract.base_salary + SalaryContract.allowances - SalaryContract.deductions
    rows = db.execute(
        select(
            Employee.country,
            func.count(Employee.id).label("emp_count"),
            func.sum(net).label("total"),
            func.avg(net).label("avg"),
        )
        .join(SalaryContract, SalaryContract.employee_id == Employee.id)
        .where(SalaryContract.is_active == True)  # noqa: E712
        .where(Employee.is_active == True)  # noqa: E712
        .group_by(Employee.country)
        .order_by(func.sum(net).desc())
    ).all()
    return [
        CountrySummary(
            country=r.country,
            employee_count=r.emp_count,
            total_net_salary=r.total or Decimal("0"),
            avg_net_salary=r.avg or Decimal("0"),
        )
        for r in rows
    ]
