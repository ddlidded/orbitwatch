from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def build_dashboard(db: Session, instrument_id: Optional[str] = None) -> dict[str, Any]:
    if instrument_id:
        instrument = db.query(models.Instrument).filter_by(id=UUID(instrument_id)).first()
    else:
        instrument = db.query(models.Instrument).order_by(models.Instrument.last_seen_at.desc()).first()

    if not instrument:
        return {
            'instrument_status': 'offline',
            'alert_count': 0,
            'target_summary': {},
        }

    current_sample = (
        db.query(models.Sample)
        .join(models.Sequence)
        .filter(
            models.Sequence.instrument_id == instrument.id,
            models.Sample.acquisition_status == 'running',
        )
        .order_by(models.Sample.started_at.desc())
        .first()
    )
    if not current_sample:
        current_sample = (
            db.query(models.Sample)
            .join(models.Sequence)
            .filter(
                models.Sequence.instrument_id == instrument.id,
                models.Sample.acquisition_status == 'completed',
            )
            .order_by(models.Sample.completed_at.desc())
            .first()
        )

    current_sequence = None
    if current_sample:
        current_sequence = current_sample.sequence
    else:
        current_sequence = (
            db.query(models.Sequence)
            .filter_by(instrument_id=instrument.id)
            .order_by(models.Sequence.started_at.desc())
            .first()
        )

    rt_live = None
    tic_live = None
    scan_number = None
    ms_order = None
    polarity = None
    progress = 0
    run_time = None
    expected_run_time = None

    if current_sample:
        latest_scan = (
            db.query(models.Scan)
            .filter_by(sample_id=current_sample.id)
            .order_by(models.Scan.retention_time_minutes.desc())
            .first()
        )
        if latest_scan:
            rt_live = float(latest_scan.retention_time_minutes)
            tic_live = float(latest_scan.tic) if latest_scan.tic is not None else None
            scan_number = latest_scan.scan_number
            ms_order = f'MS{latest_scan.ms_order}' if latest_scan.ms_order else None
            polarity = latest_scan.polarity
        if current_sample.started_at and current_sample.expected_runtime_seconds:
            started = current_sample.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if current_sample.completed_at:
                ended = current_sample.completed_at
                if ended.tzinfo is None:
                    ended = ended.replace(tzinfo=timezone.utc)
                elapsed = (ended - started).total_seconds()
                progress = 100
            else:
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                progress = min(100, int(elapsed / current_sample.expected_runtime_seconds * 100))
            run_time = elapsed / 60.0
            expected_run_time = current_sample.expected_runtime_seconds / 60.0

    alert_count = (
        db.query(func.count(models.Alert.id))
        .filter_by(instrument_id=instrument.id, status='open')
        .scalar()
    )

    target_summary = {}
    if current_sample:
        total = len(current_sample.sample_targets)
        target_summary = {'complete': 0, 'detected': 0, 'eluting': 0, 'low_intensity': 0, 'not_detected': 0, 'outside_window': 0}
        by_state = (
            db.query(models.SampleTarget.state, func.count(models.SampleTarget.id))
            .filter_by(sample_id=current_sample.id)
            .group_by(models.SampleTarget.state)
            .all()
        )
        state_map = {
            'complete': 'complete',
            'apex_candidate': 'detected',
            'low_signal': 'low_intensity',
            'not_detected': 'not_detected',
            'outside_window': 'outside_window',
        }
        for state, count in by_state:
            key = state_map.get(state, state)
            target_summary[key] = target_summary.get(key, 0) + count
        target_summary['total'] = total

    return {
        'current_sample': current_sample,
        'current_sequence': current_sequence,
        'run_time_min': run_time,
        'expected_run_time_min': expected_run_time,
        'progress_pct': progress,
        'rt_live_min': rt_live,
        'tic_live': tic_live,
        'scan_number': scan_number,
        'ms_order': ms_order,
        'polarity': polarity,
        'instrument_status': instrument.status,
        'alert_count': alert_count,
        'target_summary': target_summary,
    }


def build_peak_monitor(db: Session, instrument_id: Optional[str] = None) -> list[dict[str, Any]]:
    if instrument_id:
        instrument = db.query(models.Instrument).filter_by(id=UUID(instrument_id)).first()
    else:
        instrument = db.query(models.Instrument).order_by(models.Instrument.last_seen_at.desc()).first()
    if not instrument:
        return []
    current_sample = (
        db.query(models.Sample)
        .join(models.Sequence)
        .filter(
            models.Sequence.instrument_id == instrument.id,
            models.Sample.acquisition_status.in_(['running', 'completed']),
        )
        .order_by(models.Sample.started_at.desc())
        .first()
    )
    if not current_sample:
        return []
    rows = []
    for st in current_sample.sample_targets:
        t = st.target
        metric = (
            db.query(models.PeakMetric)
            .filter_by(sample_target_id=st.id, provisional=True)
            .order_by(models.PeakMetric.calculated_at.desc())
            .first()
        )
        if metric and metric.detection_status == 'detected':
            status = metric.quality_class or 'unknown'
            status_class = status
            rt = float(metric.observed_rt) if metric.observed_rt is not None else None
            expected_rt = float(t.expected_rt_minutes) if t.expected_rt_minutes is not None else None
            apex = float(metric.apex_intensity) if metric.apex_intensity is not None else None
            sn = float(metric.signal_to_noise) if metric.signal_to_noise is not None else None
            shape = 'Good' if status == 'good' else ('Poor' if status == 'poor' else 'OK')
            shape_class = status
            filter_val = status if status in ('good', 'warning') else 'warning'
            color = '#3ecf66' if status == 'good' else ('#f4bf18' if status == 'warning' else '#f97316')
        else:
            status = st.state or 'waiting'
            status_class = status
            rt = None
            expected_rt = float(t.expected_rt_minutes) if t.expected_rt_minutes is not None else None
            apex = None
            sn = None
            shape = '–'
            shape_class = ''
            filter_val = 'missing' if st.state in ('not_detected', 'low_signal', 'waiting') else 'warning'
            color = '#f97316' if filter_val == 'missing' else '#f4bf18'
        rows.append({
            'compound_name': t.compound_name,
            'adduct': t.adduct,
            'target_mz': float(t.target_mz),
            'status': status,
            'statusClass': status_class,
            'rt': rt,
            'expected_rt': expected_rt,
            'apex_intensity': apex,
            'sn': sn,
            'shape': shape,
            'shapeClass': shape_class,
            'filter': filter_val,
            'color': color,
        })
    return rows
