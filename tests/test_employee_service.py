"""Unit tests for EmployeeService — tests business logic via the service layer directly."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.salary_contract import SalaryContract
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services.employee_service import EmployeeService


def _make_employee(db: Session, suffix: str = "001", dept: str = "Engineering", country: str = "United States") -> Employee:
    emp = Employee(
        employee_id=f"EMP{suffix}",
        first_name="Jane",
        last_name="Smith",
        email=f"jane.smith.{suffix}@acme.com",
        department=dept,
        country=country,
        is_active=True,
    )
    db.add(emp)
    db.flush()
    return emp


def _make_contract(db: Session, emp: Employee) -> SalaryContract:
    from decimal import Decimal
    contract = SalaryContract(
        employee_id=emp.id,
        base_salary=Decimal("80000.00"),
        allowances=Decimal("5000.00"),
        deductions=Decimal("10000.00"),
        effective_from=date(2024, 1, 1),
        currency="USD",
        is_active=True,
    )
    db.add(contract)
    db.flush()
    return contract


class TestEmployeeService:
    def test_create_employee_success(self, db: Session):
        svc = EmployeeService(db)
        result = svc.create(EmployeeCreate(
            employee_id="EMP99001",
            first_name="Alice",
            last_name="Walker",
            email="alice.walker@acme.com",
            department="Engineering",
            country="United States",
        ))
        assert result.id is not None
        assert result.employee_id == "EMP99001"
        assert result.is_active is True

    def test_create_employee_duplicate_email_raises_409(self, db: Session):
        emp = _make_employee(db, "DUP001")
        svc = EmployeeService(db)
        with pytest.raises(HTTPException) as exc:
            svc.create(EmployeeCreate(
                employee_id="EMP99099",
                first_name="Bob",
                last_name="Jones",
                email=emp.email,  # same email
                department="HR",
                country="UK",
            ))
        assert exc.value.status_code == 409
        assert "Email" in exc.value.detail

    def test_create_employee_duplicate_id_raises_409(self, db: Session):
        emp = _make_employee(db, "DUP002")
        svc = EmployeeService(db)
        with pytest.raises(HTTPException) as exc:
            svc.create(EmployeeCreate(
                employee_id=emp.employee_id,  # same employee_id
                first_name="Carol",
                last_name="Davis",
                email="carol.unique@acme.com",
                department="Finance",
                country="Germany",
            ))
        assert exc.value.status_code == 409

    def test_get_by_id_not_found_raises_404(self, db: Session):
        svc = EmployeeService(db)
        with pytest.raises(HTTPException) as exc:
            svc.get_by_id(999999)
        assert exc.value.status_code == 404

    def test_list_employees_search_by_name(self, db: Session):
        _make_employee(db, "SRCH01", dept="Engineering", country="United States")
        emp2 = _make_employee(db, "SRCH02", dept="HR", country="Germany")
        emp2.last_name = "Uniquename"
        db.flush()

        svc = EmployeeService(db)
        employees, total = svc.list_employees(search="Uniquename")
        assert total >= 1
        assert any(e.last_name == "Uniquename" for e in employees)

    def test_list_employees_filter_by_department(self, db: Session):
        _make_employee(db, "DEPT01", dept="Legal", country="United States")
        _make_employee(db, "DEPT02", dept="Legal", country="Germany")
        _make_employee(db, "DEPT03", dept="Sales", country="Canada")

        svc = EmployeeService(db)
        employees, total = svc.list_employees(department="Legal")
        assert total >= 2
        assert all(e.department == "Legal" for e in employees)

    def test_list_employees_filter_by_active_status(self, db: Session):
        emp = _make_employee(db, "INACT01")
        emp.is_active = False
        db.flush()

        svc = EmployeeService(db)
        active_emps, _ = svc.list_employees(is_active=True)
        assert all(e.is_active for e in active_emps)

        inactive_emps, _ = svc.list_employees(is_active=False)
        assert all(not e.is_active for e in inactive_emps)

    def test_update_employee_partial(self, db: Session):
        emp = _make_employee(db, "UPD001")
        svc = EmployeeService(db)
        updated = svc.update(emp.id, EmployeeUpdate(department="Finance"))
        assert updated.department == "Finance"
        assert updated.first_name == emp.first_name  # unchanged

    def test_deactivate_employee(self, db: Session):
        emp = _make_employee(db, "DEL001")
        assert emp.is_active is True
        svc = EmployeeService(db)
        svc.deactivate(emp.id)
        db.refresh(emp)
        assert emp.is_active is False

    def test_get_departments_returns_distinct(self, db: Session):
        _make_employee(db, "DEPT10", dept="Legal")
        _make_employee(db, "DEPT11", dept="Legal")
        _make_employee(db, "DEPT12", dept="Marketing")
        svc = EmployeeService(db)
        depts = svc.get_departments()
        assert len(depts) == len(set(depts))  # no duplicates
        assert "Legal" in depts
        assert "Marketing" in depts
