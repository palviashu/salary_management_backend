from math import ceil

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.payroll import BatchDetail, BatchSummary, PayrollRunRequest
from app.services.payroll_service import PayrollService

router = APIRouter(prefix="/payroll", tags=["payroll"])


def _get_service(db: Session = Depends(get_db)) -> PayrollService:
    return PayrollService(db)


@router.get("/batches", response_model=PaginatedResponse[BatchSummary])
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: PayrollService = Depends(_get_service),
):
    batches, total = svc.list_batches(page=page, page_size=page_size)
    items = [
        BatchSummary(
            id=b.id,
            pay_period_start=b.pay_period_start,
            pay_period_end=b.pay_period_end,
            status=b.status,
            processed_at=b.processed_at,
            created_at=b.created_at,
        )
        for b in batches
    ]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.post("/batches", response_model=BatchSummary, status_code=status.HTTP_201_CREATED)
def run_payroll(data: PayrollRunRequest, svc: PayrollService = Depends(_get_service)):
    batch = svc.run_payroll(data.pay_period_start, data.pay_period_end)
    return BatchSummary(
        id=batch.id,
        pay_period_start=batch.pay_period_start,
        pay_period_end=batch.pay_period_end,
        status=batch.status,
        processed_at=batch.processed_at,
        created_at=batch.created_at,
    )


@router.get("/batches/{batch_id}", response_model=BatchDetail)
def get_batch_detail(
    batch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    svc: PayrollService = Depends(_get_service),
):
    batch, records, total_records, total_payroll = svc.get_batch_detail(
        batch_id, page=page, page_size=page_size
    )
    return BatchDetail(
        id=batch.id,
        pay_period_start=batch.pay_period_start,
        pay_period_end=batch.pay_period_end,
        status=batch.status,
        processed_at=batch.processed_at,
        created_at=batch.created_at,
        total_records=total_records,
        total_net_payroll=total_payroll,
        records=records,
    )


@router.post("/batches/{batch_id}/approve", response_model=BatchSummary)
def approve_batch(batch_id: int, svc: PayrollService = Depends(_get_service)):
    batch = svc.approve_batch(batch_id)
    return BatchSummary(
        id=batch.id,
        pay_period_start=batch.pay_period_start,
        pay_period_end=batch.pay_period_end,
        status=batch.status,
        processed_at=batch.processed_at,
        created_at=batch.created_at,
    )
