from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app import models
from app.tasks import store_export_file

logger = logging.getLogger(__name__)

_BRAND_DARK = colors.HexColor('#0b1320')
_BRAND_ACCENT = colors.HexColor('#3b82f6')
_BRAND_TEXT = colors.HexColor('#1e293b')
_BRAND_MUTED = colors.HexColor('#64748b')
_BRAND_LIGHT_BG = colors.HexColor('#f1f5f9')
_WHITE = colors.white


def _logo_path() -> Optional[Path]:
    candidate = Path(__file__).parent.parent / 'assets' / 'logo.png'
    if candidate.exists():
        return candidate
    candidate = Path(__file__).parent.parent.parent.parent / 'frontend' / 'public' / 'logo.png'
    if candidate.exists():
        return candidate
    return None


def _pstyle(name: str, **kwargs: Any) -> ParagraphStyle:
    base = getSampleStyleSheet()[name]
    return ParagraphStyle(name, parent=base, **kwargs)


def build_sample_report(db: Session, sample_id: str, user_id: str) -> str:
    sample = (
        db.query(models.Sample)
        .filter_by(id=UUID(sample_id))
        .first()
    )
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

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title=f'OrbitWatch Sample Report - {sample.sample_name}',
        author='isotopiq OrbitWatch',
    )

    styles = getSampleStyleSheet()
    title_style = _pstyle('Heading1', fontSize=22, textColor=_BRAND_DARK, spaceAfter=4)
    subtitle_style = _pstyle('Normal', fontSize=10, textColor=_BRAND_MUTED, spaceAfter=18)
    section_style = _pstyle('Heading2', fontSize=14, textColor=_BRAND_DARK, spaceAfter=10, spaceBefore=14)
    body_style = _pstyle('Normal', fontSize=10, textColor=_BRAND_TEXT, leading=14)
    footer_style = _pstyle('Normal', fontSize=8, textColor=_BRAND_MUTED, alignment=TA_CENTER)

    story: list[Any] = []

    # Header row: logo + title block
    header_data = []
    logo = _logo_path()
    if logo:
        img = Image(str(logo), width=1.4 * inch, height=0.7 * inch)
        img.hAlign = 'LEFT'
        header_data.append(img)
    header_data.append(
        Paragraph(
            '<b>OrbitWatch</b><br/><font size="9" color="#64748b">Sample Report</font>',
            ParagraphStyle('brand', fontSize=18, textColor=_BRAND_DARK, alignment=TA_RIGHT),
        )
    )
    header_table = Table([header_data], colWidths=[None, 4 * inch])
    header_table.setStyle(
        TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ])
    )
    story.append(header_table)
    story.append(Paragraph(sample.sample_name, title_style))
    sequence_name = sample.sequence.name if sample.sequence else '—'
    instrument_name = sample.sequence.instrument.name if sample.sequence and sample.sequence.instrument else '—'
    story.append(
        Paragraph(
            f'Instrument: {instrument_name} &nbsp;|&nbsp; Sequence: {sequence_name}',
            subtitle_style,
        )
    )
    story.append(Spacer(1, 0.1 * inch))

    # Metadata table
    meta = [
        ['Sample Name', sample.sample_name],
        ['Position', str(sample.position)],
        ['Sample Type', sample.sample_type or '—'],
        ['Method', sample.method_name or '—'],
        ['Polarity', sample.polarity or '—'],
        ['Acquisition Status', sample.acquisition_status],
        ['Generated', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')],
    ]
    meta_table = Table(meta, colWidths=[1.6 * inch, 5.4 * inch])
    meta_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), _BRAND_LIGHT_BG),
            ('TEXTCOLOR', (0, 0), (-1, -1), _BRAND_TEXT),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
    )
    story.append(Paragraph('Sample Information', section_style))
    story.append(meta_table)
    story.append(Spacer(1, 0.2 * inch))

    # Target summary
    story.append(Paragraph('Target Summary', section_style))
    sample_targets = list(sample.sample_targets)
    if sample_targets:
        target_rows = [
            [
                'Compound',
                'Adduct',
                'm/z',
                'Status',
                'RT (min)',
                'Apex Int.',
                'S/N',
            ]
        ]
        for st in sample_targets:
            target = st.target
            peak = max(st.peak_metrics, key=lambda p: p.calculated_at, default=None) if st.peak_metrics else None
            target_rows.append(
                [
                    target.compound_name,
                    target.adduct or '—',
                    f'{float(target.target_mz):.4f}',
                    (peak.detection_status if peak else st.state).replace('_', ' ').title(),
                    f'{float(peak.observed_rt):.3f}' if peak and peak.observed_rt is not None else '—',
                    f'{float(peak.apex_intensity):.3e}' if peak and peak.apex_intensity is not None else '—',
                    f'{float(peak.signal_to_noise):.1f}' if peak and peak.signal_to_noise is not None else '—',
                ]
            )

        target_table = Table(target_rows, repeatRows=1, colWidths=[1.7 * inch, 0.9 * inch, 0.9 * inch, 1.0 * inch, 0.9 * inch, 1.1 * inch, 0.9 * inch])
        target_table.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), _BRAND_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [_WHITE, _BRAND_LIGHT_BG]),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ])
        )
        story.append(target_table)
    else:
        story.append(Paragraph('No target data available for this sample.', body_style))

    # Footer note
    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            'Generated by isotopiq OrbitWatch. This report contains provisional metrics and is intended for operational review.',
            footer_style,
        )
    )

    doc.build(story)
    data = buf.getvalue()

    key = store_export_file(data, f'reports/sample_{sample_id}.pdf', 'application/pdf')
    now = datetime.now(timezone.utc)
    report.status = 'completed'
    report.file_key = key
    report.completed_at = now
    report.expires_at = now + timedelta(days=7)
    db.commit()
    return str(report.id)
