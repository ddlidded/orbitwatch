from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app import models


def get_sample_dashboard(db: Session, instrument_id: Optional[str] = None) -> Optional[models.Sample]:
    q = (
        db.query(models.Sample)
        .join(models.Sequence)
        .filter(models.Sample.acquisition_status == 'running')
    )
    if instrument_id:
        q = q.filter(models.Sequence.instrument_id == UUID(instrument_id))
    return q.order_by(models.Sample.started_at.desc()).first()


def get_latest_completed_sample(db: Session, instrument_id: str) -> Optional[models.Sample]:
    return (
        db.query(models.Sample)
        .join(models.Sequence)
        .filter(
            models.Sequence.instrument_id == UUID(instrument_id),
            models.Sample.acquisition_status == 'completed',
        )
        .order_by(models.Sample.completed_at.desc())
        .first()
    )
