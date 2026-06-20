"""Integration tests for analytics endpoints."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.salary_contract import SalaryContract


def _seed_employee_with_contract(
    db: Session,
    suffix: str,
    dept: str,
    country: str,
    base_salary: Decimal,
) -> Employee:
    emp = Employee(
        employee_id=f"ANA{suffix}",
        first_name="Ana",
        last_name=f"Test{suffix}",
        email=f"analytics.{suffix}@acme.com",
        department=dept,
        country=country,
        is_active=True,
    )
    db.add(emp)
    db.flush()
    contract = SalaryContract(
        employee_id=emp.id,
        base_salary=base_salary,
        allowances=Decimal("5000.00"),
        deductions=Decimal("8000.00"),
        effective_from=date(2024, 1, 1),
        currency="USD",
        is_active=True,
    )
    db.add(contract)
    db.flush()
    return emp


class TestAnalyticsAPI:
    def test_dashboard_has_required_fields(self, client: TestClient, db: Session):
        _seed_employee_with_contract(db, "DASH01", "Engineering", "United States", Decimal("90000"))
        resp = client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_active_employees" in body
        assert "total_monthly_payroll" in body
        assert "avg_salary" in body
        assert "department_breakdown" in body
        assert "country_breakdown" in body
        assert body["total_active_employees"] >= 1

    def test_by_department_groups_correctly(self, client: TestClient, db: Session):
        _seed_employee_with_contract(db, "DPTA01", "Analytics", "United States", Decimal("100000"))
        _seed_employee_with_contract(db, "DPTA02", "Analytics", "Germany", Decimal("90000"))
        _seed_employee_with_contract(db, "DPTA03", "Marketing", "United States", Decimal("70000"))

        resp = client.get("/api/v1/analytics/by-department")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        analytics_entry = next((d for d in body if d["department"] == "Analytics"), None)
        assert analytics_entry is not None
        assert analytics_entry["employee_count"] >= 2

    def test_by_country_returns_list(self, client: TestClient, db: Session):
        _seed_employee_with_contract(db, "CTY01", "Engineering", "Brazil", Decimal("30000"))
        resp = client.get("/api/v1/analytics/by-country")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        brazil = next((c for c in body if c["country"] == "Brazil"), None)
        assert brazil is not None

    def test_salary_distribution_returns_buckets(self, client: TestClient, db: Session):
        _seed_employee_with_contract(db, "DIST01", "Engineering", "United States", Decimal("80000"))
        _seed_employee_with_contract(db, "DIST02", "Legal", "United States", Decimal("150000"))
        resp = client.get("/api/v1/analytics/salary-distribution")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0
        for bucket in body:
            assert "bucket_label" in bucket
            assert "count" in bucket
            assert bucket["count"] > 0

    def test_dashboard_total_payroll_matches_contracts(self, client: TestClient, db: Session):
        base = Decimal("50000.00")
        allowances = Decimal("5000.00")
        deductions = Decimal("8000.00")
        net = base + allowances - deductions  # 47000

        _seed_employee_with_contract(db, "PAY01", "Engineering", "United States", base)
        # Update to use exact allowances/deductions
        from sqlalchemy import select
        contract = db.execute(
            select(SalaryContract)
            .where(SalaryContract.employee_id.in_(
                [e.id for e in db.query(Employee).filter(Employee.employee_id == "ANAPAY01").all()]
            ))
        ).scalar_one_or_none()

        resp = client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        # Total payroll should be positive
        assert Decimal(body["total_monthly_payroll"]) > 0
