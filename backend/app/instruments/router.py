from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_active_user, require_permission

router = APIRouter(prefix='/instruments', tags=['instruments'])


@router.get('', response_model=list[schemas.InstrumentOut])
def list_instruments(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('instrument:read')),
):
    return db.query(models.Instrument).order_by(models.Instrument.created_at.desc()).all()


@router.get('/{instrument_id}', response_model=schemas.InstrumentOut)
def get_instrument(
    instrument_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('instrument:read')),
):
    inst = db.query(models.Instrument).filter_by(id=UUID(instrument_id)).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Instrument not found')
    return inst


@router.get('/{instrument_id}/telemetry', response_model=list[schemas.InstrumentTelemetryOut])
def get_telemetry(
    instrument_id: str,
    metric_name: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('instrument:read')),
):
    q = db.query(models.InstrumentTelemetry).filter_by(instrument_id=UUID(instrument_id))
    if metric_name:
        q = q.filter_by(metric_name=metric_name)
    items = q.order_by(models.InstrumentTelemetry.recorded_at.desc()).limit(limit).all()
    return [schemas.InstrumentTelemetryOut.model_validate(t) for t in items]


@router.get('/{instrument_id}/alerts', response_model=schemas.PaginatedResponse)
def get_alerts(
    instrument_id: str,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('instrument:read')),
):
    from app.services import alert_service
    total, items = alert_service.list_alerts(db, instrument_id, status, severity, skip, limit)
    return {
        'total': total,
        'page': skip // limit + 1,
        'page_size': limit,
        'items': [schemas.AlertOut.model_validate(a) for a in items],
    }
