from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.salary_contract import SalaryContract
from app.schemas.salary_contract import SalaryContractCreate, SalaryContractUpdate


class ContractService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_for_employee(self, employee_id: int, data: SalaryContractCreate) -> SalaryContract:
        # Deactivate any existing active contract
        self.db.execute(
            update(SalaryContract)
            .where(SalaryContract.employee_id == employee_id, SalaryContract.is_active == True)  # noqa: E712
            .values(is_active=False)
        )
        contract = SalaryContract(employee_id=employee_id, **data.model_dump())
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def get_by_id(self, contract_id: int) -> SalaryContract:
        contract = self.db.execute(
            select(SalaryContract).where(SalaryContract.id == contract_id)
        ).scalar_one_or_none()
        if contract is None:
            raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
        return contract

    def list_for_employee(self, employee_id: int) -> list[SalaryContract]:
        result = self.db.execute(
            select(SalaryContract)
            .where(SalaryContract.employee_id == employee_id)
            .order_by(SalaryContract.effective_from.desc())
        )
        return list(result.scalars().all())

    def update(self, contract_id: int, data: SalaryContractUpdate) -> SalaryContract:
        contract = self.get_by_id(contract_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(contract, field, value)
        self.db.commit()
        self.db.refresh(contract)
        return contract
