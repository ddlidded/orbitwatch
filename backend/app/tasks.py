from __future__ import annotations

import io
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
import dramatiq
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from uuid import UUID

from app.processing.peak_detection import detect_peak

logger = logging.getLogger(__name__)

settings = get_settings()
_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(_broker)


def _s3_client():
    return boto3.client(
        's3',
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version='s3v4'),
    )


def _local_store_dir() -> Path:
    path = Path(__file__).resolve().parent.parent / 'data' / 'exports'
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_export_file(data: bytes, key: str, content_type: str) -> str:
    bucket = settings.s3_bucket
    client = _s3_client()
    try:
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)
        full_key = f'{uuid.uuid4().hex}/{key}'
        client.put_object(Bucket=bucket, Key=full_key, Body=data, ContentType=content_type)
        return full_key
    except (BotoCoreError, ClientError, Exception) as exc:
        logger.warning('S3 upload failed (%s); falling back to local file storage', exc)
        store_dir = _local_store_dir()
        full_key = f'{uuid.uuid4().hex}/{key}'
        target = store_dir / full_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f'local://{full_key}'


def get_export_file(key: str) -> bytes | None:
    if key.startswith('local://'):
        suffix = key.removeprefix('local://').lstrip('/')
        if '..' in suffix or suffix.startswith('/'):
            return None
        store_dir = _local_store_dir().resolve()
        path = (store_dir / suffix).resolve()
        if not str(path).startswith(str(store_dir)):
            return None
        if path.exists():
            return path.read_bytes()
        return None
    try:
        resp = _s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
        return resp['Body'].read()
    except Exception:
        logger.exception('Failed to retrieve export file %s', key)
        return None


def _get_db() -> Session:
    return SessionLocal()


@dramatiq.actor
def finalize_sample_processing(sample_id: str) -> None:
    from app import models

    db = _get_db()
    try:
        sample = db.query(models.Sample).filter_by(id=UUID(sample_id)).first()
        if not sample:
            return
        alg = (
            db.query(models.AlgorithmVersion)
            .filter_by(name='final_peak', version='1.0.0')
            .first()
        )
        if not alg:
            alg = models.AlgorithmVersion(name='final_peak', version='1.0.0', parameters={})
            db.add(alg)
            db.flush()

        for st in sample.sample_targets:
            points = (
                db.query(models.XicPoint)
                .filter_by(sample_target_id=st.id)
                .order_by(models.XicPoint.retention_time_minutes)
                .all()
            )
            if len(points) < 3:
                continue
            rt_array = [p.retention_time_minutes for p in points]
            intensity_array = [p.intensity for p in points]
            result = detect_peak(rt_array, intensity_array, st.target, alg, provisional=False)
            existing = (
                db.query(models.PeakMetric)
                .filter_by(sample_target_id=st.id, algorithm_version_id=alg.id, provisional=False)
                .first()
            )
            if not existing:
                existing = models.PeakMetric(
                    sample_target_id=st.id,
                    algorithm_version_id=alg.id,
                    provisional=False,
                )
                db.add(existing)
            existing.detection_status = result.detection_status
            existing.target_state = 'complete'
            existing.observed_rt = result.observed_rt
            existing.apex_intensity = result.apex_intensity
            existing.integrated_area = result.integrated_area
            existing.mass_error_ppm = result.mass_error_ppm
            existing.signal_to_noise = result.signal_to_noise
            existing.fwhm_minutes = result.fwhm_minutes
            existing.points_across_peak = result.points_across_peak
            existing.asymmetry_factor = result.asymmetry_factor
            existing.tailing_factor = result.tailing_factor
            existing.baseline_estimate = result.baseline_estimate
            existing.integration_start_rt = result.integration_start_rt
            existing.integration_end_rt = result.integration_end_rt
            existing.quality_class = result.quality_class
            existing.quality_reasons = result.quality_reasons
            existing.calculated_at = datetime.now(timezone.utc)
            st.state = 'complete'

        sample.finalization_status = 'finalized'
        db.commit()
    except Exception:
        db.rollback()
        logger.exception('Final processing failed for sample %s', sample_id)
        raise
    finally:
        db.close()
