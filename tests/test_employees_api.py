"""Integration tests for the employees API endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.salary_contract import SalaryContract
from datetime import date
from decimal import Decimal


def _make_employee(db: Session, suffix: str = "001") -> Employee:
    emp = Employee(
        employee_id=f"APITEST{suffix}",
        first_name="Test",
        last_name="User",
        email=f"api.test.{suffix}@acme.com",
        department="Engineering",
        country="United States",
        is_active=True,
    )
    db.add(emp)
    db.flush()
    return emp


class TestEmployeesAPI:
    def test_list_employees_returns_paginated(self, client: TestClient):
        resp = client.get("/api/v1/employees?page=1&page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "total_pages" in body
        assert isinstance(body["items"], list)

    def test_create_employee_returns_201(self, client: TestClient):
        resp = client.post("/api/v1/employees", json={
            "employee_id": "NEWAPI001",
            "first_name": "Alice",
            "last_name": "Wonder",
            "email": "alice.wonder.api@acme.com",
            "department": "Engineering",
            "country": "United States",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["employee_id"] == "NEWAPI001"
        assert body["is_active"] is True

    def test_create_employee_duplicate_email_returns_409(self, client: TestClient, db: Session):
        emp = _make_employee(db, "DUP01")
        resp = client.post("/api/v1/employees", json={
            "employee_id": "NEWUNIQ001",
            "first_name": "Bob",
            "last_name": "Builder",
            "email": emp.email,  # duplicate
            "department": "HR",
            "country": "Germany",
        })
        assert resp.status_code == 409

    def test_get_employee_by_id(self, client: TestClient, db: Session):
        emp = _make_employee(db, "GET01")
        resp = client.get(f"/api/v1/employees/{emp.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == emp.id
        assert body["employee_id"] == emp.employee_id

    def test_get_employee_not_found_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/employees/9999999")
        assert resp.status_code == 404

    def test_patch_employee_updates_department(self, client: TestClient, db: Session):
        emp = _make_employee(db, "UPD01")
        resp = client.patch(f"/api/v1/employees/{emp.id}", json={"department": "Finance"})
        assert resp.status_code == 200
        assert resp.json()["department"] == "Finance"

    def test_delete_employee_soft_deactivates(self, client: TestClient, db: Session):
        emp = _make_employee(db, "DEL01")
        assert emp.is_active is True
        resp = client.delete(f"/api/v1/employees/{emp.id}")
        assert resp.status_code == 204
        db.refresh(emp)
        assert emp.is_active is False

    def test_search_employees_by_name(self, client: TestClient, db: Session):
        emp = _make_employee(db, "SRCH01")
        emp.last_name = "Xyzunique"
        db.flush()
        resp = client.get("/api/v1/employees?search=Xyzunique")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_filter_employees_by_department(self, client: TestClient, db: Session):
        emp = _make_employee(db, "FILT01")
        emp.department = "LegalTestDept"
        db.flush()
        resp = client.get("/api/v1/employees?department=LegalTestDept")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert all(e["department"] == "LegalTestDept" for e in body["items"])

    def test_meta_departments_returns_list(self, client: TestClient):
        resp = client.get("/api/v1/employees/meta/departments")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_meta_countries_returns_list(self, client: TestClient):
        resp = client.get("/api/v1/employees/meta/countries")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_employee_with_contract(self, client: TestClient, db: Session):
        emp = _make_employee(db, "CONTR01")
        contract = SalaryContract(
            employee_id=emp.id,
            base_salary=Decimal("75000.00"),
            allowances=Decimal("5000.00"),
            deductions=Decimal("7000.00"),
            effective_from=date(2024, 1, 1),
            currency="USD",
            is_active=True,
        )
        db.add(contract)
        db.flush()

        resp = client.get(f"/api/v1/employees/{emp.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["contract"] is not None
        assert body["contract"]["base_salary"] == "75000.00"
        assert body["contract"]["net_salary"] == "73000.00"  # 75000 + 5000 - 7000
