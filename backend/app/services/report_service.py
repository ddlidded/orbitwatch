from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app import models
from app.tasks import store_export_file

logger = logging.getLogger(__name__)


def build_sample_report(db: Session, sample_id: str, user_id: str) -> str:
    sample = db.query(models.Sample).filter_by(id=UUID(sample_id)).first()
    if not sample:
        raise ValueError('Sample not found')
    report = models.Report(
        report_type='sample',
        requested_by_user_id=UUID(user_id),
        parameters={'sample_id': sample_id},
        status='pending',
    )
    db.add(report)
    db.commit()
    # Generate PDF in memory.
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 750, f'OrbitWatch Sample Report: {sample.sample_name}')
    c.drawString(72, 730, f'Sequence: {sample.sequence.name if sample.sequence else ""}')
    c.drawString(72, 710, f'Status: {sample.acquisition_status}')
    c.drawString(72, 690, f'Generated: {datetime.now(timezone.utc).isoformat()}')
    c.showPage()
    c.save()
    data = buf.getvalue()
    key = store_export_file(data, f'reports/sample_{sample_id}.pdf', 'application/pdf')
    report.status = 'completed'
    report.file_key = key
    report.completed_at = datetime.now(timezone.utc)
    report.expires_at = datetime.now(timezone.utc).replace(day=report.completed_at.day + 7)
    db.commit()
    return str(report.id)
