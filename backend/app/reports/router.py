from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import require_permission
from app.services import report_service

router = APIRouter(prefix='/reports', tags=['reports'])


@router.post('', response_model=schemas.ReportOut)
def create_report(
    report_type: str,
    sample_id: str | None = None,
    sequence_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('report:write')),
):
    if report_type == 'sample' and sample_id:
        report_id = report_service.build_sample_report(db, sample_id, str(user.id))
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported report type')
    report = db.query(models.Report).filter_by(id=UUID(report_id)).first()
    return report


@router.get('/{report_id}', response_model=schemas.ReportOut)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('report:read')),
):
    report = db.query(models.Report).filter_by(id=UUID(report_id)).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report not found')
    return report
