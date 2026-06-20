from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.salary_contract import SalaryContractCreate, SalaryContractRead, SalaryContractUpdate
from app.services.contract_service import ContractService
from app.services.employee_service import EmployeeService

router = APIRouter(tags=["contracts"])


def _get_contract_svc(db: Session = Depends(get_db)) -> ContractService:
    return ContractService(db)


def _get_employee_svc(db: Session = Depends(get_db)) -> EmployeeService:
    return EmployeeService(db)


@router.post(
    "/employees/{employee_id}/contracts",
    response_model=SalaryContractRead,
    status_code=status.HTTP_201_CREATED,
)
def create_contract(
    employee_id: int,
    data: SalaryContractCreate,
    emp_svc: EmployeeService = Depends(_get_employee_svc),
    contract_svc: ContractService = Depends(_get_contract_svc),
):
    emp_svc.get_by_id(employee_id)
    return contract_svc.create_for_employee(employee_id, data)


@router.get("/employees/{employee_id}/contracts", response_model=list[SalaryContractRead])
def list_contracts(
    employee_id: int,
    emp_svc: EmployeeService = Depends(_get_employee_svc),
    contract_svc: ContractService = Depends(_get_contract_svc),
):
    emp_svc.get_by_id(employee_id)
    return contract_svc.list_for_employee(employee_id)


@router.patch("/contracts/{contract_id}", response_model=SalaryContractRead)
def update_contract(
    contract_id: int,
    data: SalaryContractUpdate,
    svc: ContractService = Depends(_get_contract_svc),
):
    return svc.update(contract_id, data)
