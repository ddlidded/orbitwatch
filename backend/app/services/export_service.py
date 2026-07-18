from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app import models
from app.tasks import store_export_file

logger = logging.getLogger(__name__)


def _sanitize_csv(value: Any) -> str:
    if value is None:
        return ''
    text = str(value)
    if text and text[0] in '=+-@':
        text = "'" + text
    return text


def export_tic_csv(db: Session, sample_id: str) -> str:
    sample = db.query(models.Sample).filter_by(id=UUID(sample_id)).first()
    if not sample:
        raise ValueError('Sample not found')
    points = (
        db.query(models.TicPoint)
        .filter_by(sample_id=sample.id)
        .order_by(models.TicPoint.retention_time_minutes)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['retention_time_minutes', 'tic'])
    for p in points:
        writer.writerow([p.retention_time_minutes, p.tic])
    data = buf.getvalue().encode()
    return store_export_file(data, f'exports/tic_{sample_id}.csv', 'text/csv')


def export_xic_csv(db: Session, sample_target_id: str) -> str:
    st = db.query(models.SampleTarget).filter_by(id=UUID(sample_target_id)).first()
    if not st:
        raise ValueError('Sample target not found')
    points = (
        db.query(models.XicPoint)
        .filter_by(sample_target_id=st.id)
        .order_by(models.XicPoint.retention_time_minutes)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            'retention_time_minutes',
            'intensity',
            'observed_centroid_mz',
            'mass_error_ppm',
            'provisional',
        ]
    )
    for p in points:
        writer.writerow(
            [
                p.retention_time_minutes,
                p.intensity,
                p.observed_centroid_mz,
                p.mass_error_ppm,
                p.provisional,
            ]
        )
    data = buf.getvalue().encode()
    return store_export_file(data, f'exports/xic_{sample_target_id}.csv', 'text/csv')
