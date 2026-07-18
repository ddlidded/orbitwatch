from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def create_alert(
    db: Session,
    instrument_id: str,
    category: str,
    severity: str,
    message: str,
    sequence_id: Optional[str] = None,
    sample_id: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> models.Alert:
    # Deduplicate within the last 60 seconds for same category/instrument.
    cutoff = datetime.now(timezone.utc).timestamp() - 60
    existing = (
        db.query(models.Alert)
        .filter(
            models.Alert.instrument_id == UUID(instrument_id),
            models.Alert.category == category,
            models.Alert.sample_id == (UUID(sample_id) if sample_id else None),
            models.Alert.target_id == (UUID(target_id) if target_id else None),
            func.extract('epoch', models.Alert.last_seen_at) >= cutoff,
        )
        .first()
    )
    if existing:
        existing.occurrence_count += 1
        existing.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        return existing

    alert = models.Alert(
        instrument_id=UUID(instrument_id),
        sequence_id=UUID(sequence_id) if sequence_id else None,
        sample_id=UUID(sample_id) if sample_id else None,
        target_id=UUID(target_id) if target_id else None,
        category=category,
        severity=severity,
        message=message,
        meta=metadata or {},
    )
    db.add(alert)
    db.commit()
    return alert


def list_alerts(
    db: Session,
    instrument_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    q = db.query(models.Alert)
    if instrument_id:
        q = q.filter_by(instrument_id=UUID(instrument_id))
    if status:
        q = q.filter_by(status=status)
    if severity:
        q = q.filter_by(severity=severity)
    total = q.count()
    items = q.order_by(models.Alert.last_seen_at.desc()).offset(skip).limit(limit).all()
    return total, items


def acknowledge_alert(
    db: Session, alert_id: str, user_id: str, notes: Optional[str] = None
) -> models.Alert:
    alert = db.query(models.Alert).filter_by(id=UUID(alert_id)).first()
    if not alert:
        raise ValueError('Alert not found')
    alert.status = 'acknowledged'
    alert.acknowledged_by_user_id = UUID(user_id)
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.notes = notes
    db.add(
        models.AlertAcknowledgment(
            alert_id=alert.id,
            acknowledged_by_user_id=UUID(user_id),
            notes=notes,
        )
    )
    db.commit()
    return alert
