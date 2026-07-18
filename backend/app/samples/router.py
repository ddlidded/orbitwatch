from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import require_permission
from app.services import sequence_service

router = APIRouter(prefix='/samples', tags=['samples'])


@router.get('/{sample_id}', response_model=schemas.SampleOut)
def get_sample(
    sample_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sample:read')),
):
    sample = sequence_service.get_sample(db, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Sample not found')
    return sample


@router.get('/{sample_id}/tic', response_model=dict)
def get_tic(
    sample_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50000, ge=1, le=200000),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sample:read')),
):
    total, items = sequence_service.get_tic_points(db, sample_id, skip, limit)
    return {'total': total, 'items': [schemas.TicPointOut.model_validate(p) for p in items]}


@router.get('/{sample_id}/targets', response_model=list[schemas.SampleTargetOut])
def get_sample_targets(
    sample_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sample:read')),
):
    items = (
        db.query(models.SampleTarget)
        .filter_by(sample_id=UUID(sample_id))
        .all()
    )
    return [schemas.SampleTargetOut.model_validate(st) for st in items]


@router.get('/{sample_id}/targets/{target_id}/xic', response_model=list[schemas.XicPointOut])
def get_xic(
    sample_id: str,
    target_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sample:read')),
):
    st = (
        db.query(models.SampleTarget)
        .filter_by(sample_id=UUID(sample_id), target_id=UUID(target_id))
        .first()
    )
    if not st:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Sample target not found')
    points = (
        db.query(models.XicPoint)
        .filter_by(sample_target_id=st.id)
        .order_by(models.XicPoint.retention_time_minutes)
        .all()
    )
    return [schemas.XicPointOut.model_validate(p) for p in points]


@router.get('/{sample_id}/targets/{target_id}/peak', response_model=Optional[schemas.PeakMetricOut])
def get_peak(
    sample_id: str,
    target_id: str,
    provisional: bool = True,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sample:read')),
):
    st = (
        db.query(models.SampleTarget)
        .filter_by(sample_id=UUID(sample_id), target_id=UUID(target_id))
        .first()
    )
    if not st:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Sample target not found')
    metric = (
        db.query(models.PeakMetric)
        .filter_by(sample_target_id=st.id, provisional=provisional)
        .order_by(models.PeakMetric.calculated_at.desc())
        .first()
    )
    return metric
