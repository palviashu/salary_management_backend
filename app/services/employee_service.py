from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.employee import Employee
from app.models.salary_contract import SalaryContract
from app.schemas.employee import EmployeeCreate, EmployeeUpdate


class EmployeeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_employees(
        self,
        search: str | None = None,
        department: str | None = None,
        country: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "last_name",
        sort_dir: str = "asc",
    ) -> tuple[list[Employee], int]:
        stmt = select(Employee)

        filters = []
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Employee.first_name.ilike(pattern),
                    Employee.last_name.ilike(pattern),
                    Employee.employee_id.ilike(pattern),
                    Employee.email.ilike(pattern),
                )
            )
        if department:
            filters.append(Employee.department == department)
        if country:
            filters.append(Employee.country == country)
        if is_active is not None:
            filters.append(Employee.is_active == is_active)

        if filters:
            from sqlalchemy import and_
            stmt = stmt.where(and_(*filters))

        count_stmt = select(func.count()).select_from(Employee)
        if filters:
            from sqlalchemy import and_
            count_stmt = count_stmt.where(and_(*filters))

        total = self.db.execute(count_stmt).scalar_one()

        sort_col = getattr(Employee, sort_by, Employee.last_name)
        stmt = stmt.order_by(sort_col.asc() if sort_dir == "asc" else sort_col.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        employees = list(self.db.execute(stmt).scalars().all())
        return employees, total

    def get_by_id(self, employee_id: int) -> Employee:
        stmt = (
            select(Employee)
            .where(Employee.id == employee_id)
            .options(selectinload(Employee.all_contracts))
        )
        emp = self.db.execute(stmt).scalar_one_or_none()
        if emp is None:
            raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
        return emp

    def create(self, data: EmployeeCreate) -> Employee:
        existing = self.db.execute(
            select(Employee).where(
                (Employee.email == data.email) | (Employee.employee_id == data.employee_id)
            )
        ).scalar_one_or_none()
        if existing:
            if existing.email == data.email:
                raise HTTPException(status_code=409, detail="Email already in use")
            raise HTTPException(status_code=409, detail="Employee ID already in use")

        emp = Employee(**data.model_dump())
        self.db.add(emp)
        self.db.commit()
        self.db.refresh(emp)
        return emp

    def update(self, employee_id: int, data: EmployeeUpdate) -> Employee:
        emp = self.get_by_id(employee_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(emp, field, value)
        self.db.commit()
        self.db.refresh(emp)
        return emp

    def deactivate(self, employee_id: int) -> None:
        emp = self.get_by_id(employee_id)
        emp.is_active = False
        self.db.commit()

    def get_departments(self) -> list[str]:
        result = self.db.execute(
            select(Employee.department).distinct().order_by(Employee.department)
        )
        return [r[0] for r in result.all()]

    def get_countries(self) -> list[str]:
        result = self.db.execute(
            select(Employee.country).distinct().order_by(Employee.country)
        )
        return [r[0] for r in result.all()]
