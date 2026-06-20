from math import ceil

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate, EmployeeWithContract
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/employees", tags=["employees"])


def _get_service(db: Session = Depends(get_db)) -> EmployeeService:
    return EmployeeService(db)


@router.get("", response_model=PaginatedResponse[EmployeeRead])
def list_employees(
    search: str | None = Query(None, description="Search by name, email or employee ID"),
    department: str | None = None,
    country: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("last_name", pattern="^(last_name|first_name|department|country|created_at)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    svc: EmployeeService = Depends(_get_service),
):
    employees, total = svc.list_employees(
        search=search,
        department=department,
        country=country,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return PaginatedResponse(
        items=employees,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(data: EmployeeCreate, svc: EmployeeService = Depends(_get_service)):
    return svc.create(data)


@router.get("/meta/departments", response_model=list[str])
def list_departments(svc: EmployeeService = Depends(_get_service)):
    return svc.get_departments()


@router.get("/meta/countries", response_model=list[str])
def list_countries(svc: EmployeeService = Depends(_get_service)):
    return svc.get_countries()


@router.get("/{employee_id}", response_model=EmployeeWithContract)
def get_employee(employee_id: int, svc: EmployeeService = Depends(_get_service)):
    emp = svc.get_by_id(employee_id)
    active_contract = next((c for c in emp.all_contracts if c.is_active), None)
    return {
        "id": emp.id,
        "employee_id": emp.employee_id,
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "email": emp.email,
        "department": emp.department,
        "country": emp.country,
        "is_active": emp.is_active,
        "created_at": emp.created_at,
        "contract": active_contract,
    }


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    svc: EmployeeService = Depends(_get_service),
):
    return svc.update(employee_id, data)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_employee(employee_id: int, svc: EmployeeService = Depends(_get_service)):
    svc.deactivate(employee_id)
