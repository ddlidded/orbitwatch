from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.audit import log_event
from app.database import get_db
from app.security import get_current_active_user, require_permission
from app.services import alert_service

router = APIRouter(prefix='/alerts', tags=['alerts'])


@router.get('', response_model=schemas.PaginatedResponse)
def list_alerts(
    instrument_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('alert:read')),
):
    total, items = alert_service.list_alerts(db, instrument_id, status, severity, skip, limit)
    return {
        'total': total,
        'page': skip // limit + 1,
        'page_size': limit,
        'items': [schemas.AlertOut.model_validate(a) for a in items],
    }


@router.post('/{alert_id}/acknowledge', response_model=schemas.AlertOut)
def acknowledge_alert(
    alert_id: str,
    data: schemas.AlertAcknowledge,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('alert:ack')),
):
    alert = alert_service.acknowledge_alert(db, alert_id, str(user.id), data.notes)
    log_event(
        db,
        'alert_acknowledge',
        'alert',
        resource_id=str(alert.id),
        actor_user_id=str(user.id),
        after={'status': 'acknowledged'},
    )
    return alert
