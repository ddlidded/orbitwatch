from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import DashboardSummary
from app.security import require_permission
from app.services import dashboard_service
from app.services.sequence_service import get_sample, get_sequence

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


@router.get('/summary', response_model=DashboardSummary)
def dashboard_summary(
    instrument_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('instrument:read')),
):
    data = dashboard_service.build_dashboard(db, instrument_id)
    return DashboardSummary(**data)


@router.get('/peak-monitor')
def peak_monitor(
    instrument_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('instrument:read')),
):
    return dashboard_service.build_peak_monitor(db, instrument_id)
