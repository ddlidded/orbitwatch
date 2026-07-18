from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app import models
from app.realtime.manager import manager as realtime_manager


def create_sequence(db: Session, instrument_id: str | UUID, payload: dict[str, Any]) -> models.Sequence:
    seq = models.Sequence(
        instrument_id=UUID(str(instrument_id)),
        external_sequence_id=payload.get('external_sequence_id'),
        name=payload.get('sequence_name', 'Unnamed Sequence'),
        source_path=payload.get('source_path'),
        started_at=_parse_iso(payload.get('started_at')) or datetime.now(timezone.utc),
        status='running',
        sample_count=len(payload.get('samples', [])),
        source_snapshot=payload,
    )
    db.add(seq)
    db.flush()
    for pos, s in enumerate(payload.get('samples', []), start=1):
        db.add(
            models.Sample(
                sequence_id=seq.id,
                external_sample_id=s.get('external_sample_id'),
                position=s.get('position', pos),
                sample_name=s.get('sample_name', f'Sample {pos}'),
                sample_type=s.get('sample_type'),
                method_name=s.get('method_name'),
                polarity=s.get('polarity'),
                vial_position=s.get('vial_position'),
                raw_file_name=s.get('raw_file_name'),
                expected_runtime_seconds=s.get('expected_runtime_seconds'),
                acquisition_status=s.get('status', 'queued'),
            )
        )
    db.flush()
    return seq


def get_sequence(db: Session, sequence_id: str) -> Optional[models.Sequence]:
    return db.query(models.Sequence).filter_by(id=UUID(sequence_id)).first()


def list_sequences(db: Session, instrument_id: Optional[str] = None, skip: int = 0, limit: int = 100):
    q = db.query(models.Sequence)
    if instrument_id:
        q = q.filter_by(instrument_id=UUID(instrument_id))
    total = q.count()
    items = q.order_by(models.Sequence.created_at.desc()).offset(skip).limit(limit).all()
    return total, items


def list_samples(db: Session, sequence_id: str, skip: int = 0, limit: int = 100):
    q = db.query(models.Sample).filter_by(sequence_id=UUID(sequence_id))
    total = q.count()
    items = q.order_by(models.Sample.position).offset(skip).limit(limit).all()
    return total, items


def get_sample(db: Session, sample_id: str) -> Optional[models.Sample]:
    return db.query(models.Sample).filter_by(id=UUID(sample_id)).first()


def get_tic_points(db: Session, sample_id: str, skip: int = 0, limit: int = 50000):
    q = (
        db.query(models.TicPoint)
        .filter_by(sample_id=UUID(sample_id))
        .order_by(models.TicPoint.retention_time_minutes)
    )
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return total, items


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def broadcast_sequence_update(sequence: models.Sequence) -> None:
    from asyncio import get_event_loop
    try:
        loop = get_event_loop()
        loop.create_task(
            realtime_manager.broadcast(
                f'instrument:{sequence.instrument_id}',
                {'type': 'sequence.updated', 'sequence_id': str(sequence.id), 'status': sequence.status},
            )
        )
    except Exception:
        pass


def _sample_progress(sample: models.Sample) -> int:
    if sample.acquisition_status == 'completed':
        return 100
    if not sample.started_at or not sample.expected_runtime_seconds:
        return 0
    from datetime import datetime, timezone
    elapsed = (datetime.now(timezone.utc) - sample.started_at).total_seconds()
    return min(100, max(0, int(elapsed / sample.expected_runtime_seconds * 100)))


def broadcast_sample_update(sample: models.Sample) -> None:
    from asyncio import get_event_loop
    try:
        loop = get_event_loop()
        loop.create_task(
            realtime_manager.broadcast(
                f'sequence:{sample.sequence_id}',
                {
                    'type': 'sample.updated',
                    'sample_id': str(sample.id),
                    'status': sample.acquisition_status,
                    'progress': _sample_progress(sample),
                },
            )
        )
    except Exception:
        pass


def broadcast_scan_update(sample: models.Sample, scan: models.Scan) -> None:
    from asyncio import get_event_loop
    try:
        loop = get_event_loop()
        loop.create_task(
            realtime_manager.broadcast(
                f'sample:{sample.id}',
                {
                    'type': 'scan',
                    'scan_number': scan.scan_number,
                    'retention_time_minutes': float(scan.retention_time_minutes),
                    'tic': float(scan.tic) if scan.tic is not None else None,
                    'ms_order': scan.ms_order,
                    'polarity': scan.polarity,
                },
            )
        )
    except Exception:
        pass


def broadcast_telemetry_update(instrument: models.Instrument, metrics: list[dict[str, Any]]) -> None:
    from asyncio import get_event_loop
    try:
        loop = get_event_loop()
        loop.create_task(
            realtime_manager.broadcast(
                f'instrument:{instrument.id}',
                {'type': 'telemetry.batch', 'metrics': metrics},
            )
        )
    except Exception:
        pass
