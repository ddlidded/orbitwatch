from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.processing.peak_detection import detect_peak
from app.processing.xic import calculate_tic, extract_xic_intensity
from app.processing.telemetry import evaluate_telemetry_alerts
from app.realtime.manager import manager as realtime_manager
from app.services import alert_service, sequence_service, target_service
from app.tasks import finalize_sample_processing

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dedup_message(db: Session, agent_id: str, message_id: str, message_type: str) -> bool:
    from uuid import UUID

    existing = (
        db.query(models.IngestedMessage)
        .filter_by(message_id=str(message_id), agent_id=UUID(agent_id))
        .first()
    )
    if existing:
        return True
    db.add(
        models.IngestedMessage(
            message_id=str(message_id),
            agent_id=UUID(agent_id),
            message_type=message_type,
        )
    )
    return False


def _get_or_create_instrument(
    db: Session,
    serial: str,
    name: str,
    model: str,
    **kwargs,
) -> models.Instrument:
    inst = db.query(models.Instrument).filter_by(serial_number=serial).first()
    if not inst:
        inst = models.Instrument(
            serial_number=serial,
            name=name,
            model=model,
            **kwargs,
        )
        db.add(inst)
        db.flush()
    return inst


def _ensure_algorithm_version(db: Session, name: str, version: str) -> models.AlgorithmVersion:
    av = db.query(models.AlgorithmVersion).filter_by(name=name, version=version).first()
    if not av:
        av = models.AlgorithmVersion(name=name, version=version, parameters={})
        db.add(av)
        db.flush()
    return av


def handle_agent_register(
    db: Session,
    payload: dict[str, Any],
    capabilities: dict[str, bool],
) -> dict[str, Any]:
    from app.security import generate_token, hash_token

    serial = payload['instrument_serial']
    name = payload.get('instrument_name') or serial
    model = payload.get('model', 'Orbitrap Exploris 480')
    inst = _get_or_create_instrument(
        db,
        serial=serial,
        name=name,
        model=model,
        api_version=payload.get('api_version'),
        tune_version=payload.get('tune_version'),
        iapi_version=payload.get('iapi_version'),
        agent_version=payload.get('agent_version'),
        status='online',
        last_seen_at=_now(),
    )
    agent = models.InstrumentAgent(
        instrument_id=inst.id,
        hostname=payload.get('hostname', 'unknown'),
        agent_version=payload.get('agent_version', 'unknown'),
        last_heartbeat_at=_now(),
        meta=payload.get('metadata', {}),
    )
    db.add(agent)
    db.flush()

    for key, val in capabilities.items():
        db.add(models.AgentCapability(agent_id=agent.id, capability_key=key, capability_value=bool(val)))

    token = generate_token(48)
    db.add(
        models.AgentCredential(
            agent_id=agent.id,
            token_hash=hash_token(token),
            scopes=['agent:send'],
        )
    )
    db.commit()
    return {
        'agent_id': str(agent.id),
        'instrument_id': str(inst.id),
        'token': token,
    }


def handle_agent_heartbeat(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> None:
    agent.last_heartbeat_at = _now()
    if agent.instrument:
        agent.instrument.last_seen_at = _now()
        agent.instrument.status = payload.get('status', 'online')
    db.commit()


def handle_sequence_started(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> models.Sequence:
    existing = (
        db.query(models.Sequence)
        .filter_by(
            instrument_id=agent.instrument_id,
            external_sequence_id=payload.get('external_sequence_id'),
        )
        .first()
    )
    if existing:
        seq = existing
        seq.status = 'running'
    else:
        seq = sequence_service.create_sequence(db, agent.instrument_id, payload)
    db.commit()
    # Prime samples with current target list for this instrument/method.
    for sample in seq.samples:
        _prime_sample_targets(db, sample, payload.get('method_name'))
    db.commit()
    sequence_service.broadcast_sequence_update(seq)
    return seq


def _prime_sample_targets(
    db: Session, sample: models.Sample, method_name: Optional[str]
) -> None:
    assignments = (
        db.query(models.TargetAssignment)
        .filter(
            models.TargetAssignment.instrument_id == sample.sequence.instrument_id,
            models.TargetAssignment.sequence_id.is_(None) | (models.TargetAssignment.sequence_id == sample.sequence_id),
        )
        .all()
    )
    target_list_ids = {a.target_list_id for a in assignments if a.target_list.active_version_id}
    for tl_id in target_list_ids:
        tl = db.query(models.TargetList).filter_by(id=tl_id).first()
        if not tl or not tl.active_version:
            continue
        for target in tl.active_version.targets:
            existing = (
                db.query(models.SampleTarget)
                .filter_by(sample_id=sample.id, target_id=target.id)
                .first()
            )
            if existing:
                continue
            db.add(
                models.SampleTarget(
                    sample_id=sample.id,
                    target_id=target.id,
                    state='waiting',
                )
            )


def _find_sample(
    db: Session, instrument_id: str, external_sequence_id: str, external_sample_id: str
) -> Optional[models.Sample]:
    from uuid import UUID

    return (
        db.query(models.Sample)
        .join(models.Sequence)
        .filter(
            models.Sequence.instrument_id == UUID(instrument_id),
            models.Sequence.external_sequence_id == external_sequence_id,
            models.Sample.external_sample_id == external_sample_id,
        )
        .first()
    )


def _get_or_create_sequence(
    db: Session,
    agent: models.InstrumentAgent,
    external_sequence_id: Optional[str],
    sequence_name: Optional[str] = None,
    source_path: Optional[str] = None,
) -> models.Sequence:
    from uuid import UUID

    if external_sequence_id:
        seq = (
            db.query(models.Sequence)
            .filter(
                models.Sequence.instrument_id == UUID(str(agent.instrument_id)),
                models.Sequence.external_sequence_id == external_sequence_id,
            )
            .first()
        )
        if seq:
            return seq
    seq = models.Sequence(
        instrument_id=UUID(str(agent.instrument_id)),
        external_sequence_id=external_sequence_id or f"SEQ-{uuid.uuid4().hex[:8]}",
        name=sequence_name or external_sequence_id or "Active Sequence",
        source_path=source_path,
        started_at=_now(),
        status="running",
        sample_count=0,
        source_snapshot={},
    )
    db.add(seq)
    db.flush()
    return seq


def _get_or_create_sample(
    db: Session,
    sequence: models.Sequence,
    external_sample_id: str,
    payload: dict[str, Any],
) -> models.Sample:
    sample = (
        db.query(models.Sample)
        .filter_by(
            sequence_id=sequence.id,
            external_sample_id=external_sample_id,
        )
        .first()
    )
    if sample:
        return sample
    sample = models.Sample(
        sequence_id=sequence.id,
        external_sample_id=external_sample_id,
        position=payload.get("position") or sequence.sample_count + 1,
        sample_name=payload.get("sample_name") or external_sample_id,
        sample_type=payload.get("sample_type") or "unknown",
        method_name=payload.get("method_name"),
        polarity=payload.get("polarity") or "positive",
        vial_position=payload.get("vial_position"),
        raw_file_name=payload.get("raw_file_name"),
        expected_runtime_seconds=payload.get("expected_runtime_seconds"),
        started_at=_now(),
        acquisition_status="running",
    )
    db.add(sample)
    sequence.sample_count += 1
    db.flush()
    return sample


def handle_sample_started(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> Optional[models.Sample]:
    seq = _get_or_create_sequence(
        db,
        agent,
        payload.get('external_sequence_id'),
        payload.get('sequence_name'),
        payload.get('source_path'),
    )
    sample = _get_or_create_sample(db, seq, payload['external_sample_id'], payload)
    sample.started_at = _parse_iso(payload.get('started_at')) or _now()
    sample.acquisition_status = 'running'
    db.commit()
    sequence_service.broadcast_sample_update(sample)
    return sample


def handle_scan(
    db: Session, agent: models.InstrumentAgent, envelope: dict[str, Any], payload: dict[str, Any]
) -> Optional[models.Scan]:
    seq = _get_or_create_sequence(db, agent, payload.get('external_sequence_id'))
    sample = _get_or_create_sample(
        db,
        seq,
        payload['external_sample_id'],
        {
            'sample_name': payload.get('external_sample_id'),
            'sample_type': 'unknown',
            'polarity': payload.get('polarity'),
        },
    )

    scan_number = payload['scan_number']
    agent_scan_id = str(envelope['messageId'])
    existing = (
        db.query(models.Scan)
        .filter_by(sample_id=sample.id, scan_number=scan_number, agent_scan_id=agent_scan_id)
        .first()
    )
    if existing:
        return existing

    rt = payload['retention_time_minutes']
    tic = payload.get('tic')
    tic_source = payload.get('tic_source', 'unknown')
    if tic is None and 'intensity_array' in payload:
        tic = calculate_tic(payload['intensity_array'])
        tic_source = 'calculated'

    scan = models.Scan(
        sample_id=sample.id,
        agent_scan_id=agent_scan_id,
        scan_number=scan_number,
        retention_time_minutes=rt,
        acquired_at=_parse_iso(payload.get('acquired_at')) or _now(),
        ms_order=payload.get('ms_order', 1),
        polarity=payload.get('polarity', 'positive'),
        scan_type=payload.get('scan_type'),
        tic=tic,
        tic_source=tic_source,
        base_peak_mz=payload.get('base_peak_mz'),
        base_peak_intensity=payload.get('base_peak_intensity'),
        low_mz=payload.get('low_mz'),
        high_mz=payload.get('high_mz'),
        ingestion_sequence_number=envelope['sequenceNumber'],
    )
    db.add(scan)
    db.flush()

    if tic is not None:
        db.add(
            models.TicPoint(
                sample_id=sample.id,
                scan_id=scan.id,
                retention_time_minutes=rt,
                tic=tic,
            )
        )

    xic_points = payload.get('xic_points', [])
    if xic_points:
        _store_xic_points(db, sample, scan, xic_points)
    elif 'mz_array' in payload and 'intensity_array' in payload:
        _compute_xic_points(
            db,
            sample,
            scan,
            payload['mz_array'],
            payload['intensity_array'],
        )

    _update_sample_progress(db, sample, rt)
    db.commit()
    sequence_service.broadcast_scan_update(sample, scan)
    return scan


def _store_xic_points(
    db: Session,
    sample: models.Sample,
    scan: models.Scan,
    xic_points: list[dict[str, Any]],
) -> None:
    for point in xic_points:
        sample_target_id = point.get('sample_target_id')
        if not sample_target_id:
            continue
        st = db.query(models.SampleTarget).filter_by(id=sample_target_id, sample_id=sample.id).first()
        if not st:
            continue
        existing = (
            db.query(models.XicPoint)
            .filter_by(sample_target_id=st.id, scan_id=scan.id)
            .first()
        )
        if existing:
            continue
        db.add(
            models.XicPoint(
                sample_target_id=st.id,
                scan_id=scan.id,
                retention_time_minutes=scan.retention_time_minutes,
                intensity=point['intensity'],
                observed_centroid_mz=point.get('observed_centroid_mz'),
                mass_error_ppm=point.get('mass_error_ppm'),
                provisional=True,
            )
        )
        _recalculate_provisional_peak(db, st, scan.retention_time_minutes)


def _compute_xic_points(
    db: Session,
    sample: models.Sample,
    scan: models.Scan,
    mz_array: list[float],
    intensity_array: list[float],
) -> None:
    for st in sample.sample_targets:
        target = st.target
        extracted = extract_xic_intensity(
            mz_array,
            intensity_array,
            target.target_mz,
            target.tolerance_value,
            target.tolerance_unit,
            scan.polarity,
            target.polarity,
        )
        if not extracted:
            continue
        existing = (
            db.query(models.XicPoint)
            .filter_by(sample_target_id=st.id, scan_id=scan.id)
            .first()
        )
        if existing:
            continue
        db.add(
            models.XicPoint(
                sample_target_id=st.id,
                scan_id=scan.id,
                retention_time_minutes=scan.retention_time_minutes,
                intensity=extracted['intensity'],
                observed_centroid_mz=extracted['observed_centroid_mz'],
                mass_error_ppm=extracted['mass_error_ppm'],
                provisional=True,
            )
        )
        _recalculate_provisional_peak(db, st, scan.retention_time_minutes)


def _recalculate_provisional_peak(db: Session, sample_target: models.SampleTarget, up_to_rt: float) -> None:
    points = (
        db.query(models.XicPoint)
        .filter(
            models.XicPoint.sample_target_id == sample_target.id,
            models.XicPoint.provisional == True,
            models.XicPoint.retention_time_minutes <= up_to_rt,
        )
        .order_by(models.XicPoint.retention_time_minutes)
        .all()
    )
    if len(points) < 3:
        return
    rt_array = [p.retention_time_minutes for p in points]
    intensity_array = [p.intensity for p in points]
    alg = _ensure_algorithm_version(db, 'provisional_peak', '1.0.0')
    result = detect_peak(
        rt_array,
        intensity_array,
        sample_target.target,
        alg,
        provisional=True,
    )
    # Update or create provisional PeakMetric.
    metric = (
        db.query(models.PeakMetric)
        .filter_by(sample_target_id=sample_target.id, algorithm_version_id=alg.id, provisional=True)
        .first()
    )
    if not metric:
        metric = models.PeakMetric(
            sample_target_id=sample_target.id,
            algorithm_version_id=alg.id,
            provisional=True,
        )
        db.add(metric)
    _apply_peak_result(metric, result)
    sample_target.state = result.target_state


def _apply_peak_result(metric: models.PeakMetric, result: detect_peak.__class__) -> None:
    metric.detection_status = result.detection_status
    metric.target_state = result.target_state
    metric.observed_rt = result.observed_rt
    metric.apex_intensity = result.apex_intensity
    metric.integrated_area = result.integrated_area
    metric.mass_error_ppm = result.mass_error_ppm
    metric.signal_to_noise = result.signal_to_noise
    metric.fwhm_minutes = result.fwhm_minutes
    metric.points_across_peak = result.points_across_peak
    metric.asymmetry_factor = result.asymmetry_factor
    metric.tailing_factor = result.tailing_factor
    metric.baseline_estimate = result.baseline_estimate
    metric.integration_start_rt = result.integration_start_rt
    metric.integration_end_rt = result.integration_end_rt
    metric.quality_class = result.quality_class
    metric.quality_reasons = result.quality_reasons
    metric.calculated_at = _now()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _update_sample_progress(db: Session, sample: models.Sample, current_rt: float) -> None:
    # Progress is computed on demand by SampleOut; nothing to persist here.
    pass


def handle_telemetry_batch(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> None:
    instrument = agent.instrument
    if not instrument:
        return
    sample = None
    if payload.get('external_sample_id') and payload.get('external_sequence_id'):
        sample = _find_sample(
            db,
            str(agent.instrument_id),
            payload['external_sequence_id'],
            payload['external_sample_id'],
        )
    metrics = payload.get('metrics', [])
    for m in metrics:
        db.add(
            models.InstrumentTelemetry(
                instrument_id=instrument.id,
                sample_id=sample.id if sample else None,
                metric_name=m['metric_name'],
                metric_value=m['metric_value'],
                unit=m.get('unit'),
                recorded_at=_parse_iso(m.get('recorded_at')) or _now(),
            )
        )
    db.commit()
    evaluate_telemetry_alerts(db, instrument, metrics)
    sequence_service.broadcast_telemetry_update(instrument, metrics)


def handle_sample_completed(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> Optional[models.Sample]:
    seq = _get_or_create_sequence(db, agent, payload.get('external_sequence_id'))
    sample = _get_or_create_sample(
        db,
        seq,
        payload['external_sample_id'],
        {
            'sample_name': payload.get('external_sample_id'),
            'sample_type': 'unknown',
        },
    )
    sample.acquisition_status = 'completed'
    sample.completed_at = _parse_iso(payload.get('completed_at')) or _now()
    sample.finalization_status = 'finalizing'
    db.commit()
    finalize_sample_processing.send(str(sample.id))
    sequence_service.broadcast_sample_update(sample)
    return sample


def handle_sample_failed(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> Optional[models.Sample]:
    seq = _get_or_create_sequence(db, agent, payload.get('external_sequence_id'))
    sample = _get_or_create_sample(
        db,
        seq,
        payload['external_sample_id'],
        {
            'sample_name': payload.get('external_sample_id'),
            'sample_type': 'unknown',
        },
    )
    sample.acquisition_status = 'failed'
    sample.error_message = payload.get('error_message')
    sample.completed_at = _parse_iso(payload.get('completed_at')) or _now()
    db.commit()
    alert_service.create_alert(
        db,
        instrument_id=agent.instrument_id,
        sample_id=sample.id,
        category='acquisition_failure',
        severity='error',
        message=sample.error_message or 'Sample acquisition failed',
    )
    sequence_service.broadcast_sample_update(sample)
    return sample


def handle_sequence_completed(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> Optional[models.Sequence]:
    seq = _get_or_create_sequence(
        db,
        agent,
        payload.get('external_sequence_id'),
        payload.get('sequence_name'),
        payload.get('source_path'),
    )
    seq.status = 'completed'
    seq.completed_at = _parse_iso(payload.get('completed_at')) or _now()
    db.commit()
    sequence_service.broadcast_sequence_update(seq)
    return seq


def handle_rawfile_available(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> Optional[models.Sample]:
    seq = _get_or_create_sequence(db, agent, payload.get('external_sequence_id'))
    sample = _get_or_create_sample(
        db,
        seq,
        payload['external_sample_id'],
        {
            'sample_name': payload.get('external_sample_id'),
            'sample_type': 'unknown',
        },
    )
    sample.raw_file_name = payload.get('raw_file_name')
    db.commit()
    sequence_service.broadcast_sample_update(sample)
    return sample


def handle_agent_warning(
    db: Session, agent: models.InstrumentAgent, payload: dict[str, Any]
) -> None:
    alert_service.create_alert(
        db,
        instrument_id=agent.instrument_id,
        category=payload.get('category', 'agent_warning'),
        severity=payload.get('severity', 'warning'),
        message=payload.get('message', 'Agent warning'),
        metadata=payload.get('meta', {}),
    )


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
