from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import alert_service


def evaluate_telemetry_alerts(
    db: Session, instrument: models.Instrument, metrics: list[dict[str, Any]]
) -> None:
    # Basic telemetry threshold checks.
    for m in metrics:
        name = m.get('metric_name', '').lower()
        value = m.get('metric_value')
        if value is None:
            continue
        if name == 'spray_voltage' and value < 0.5:
            alert_service.create_alert(
                db,
                instrument_id=str(instrument.id),
                category='spray_voltage_instability',
                severity='error',
                message=f'Spray voltage collapsed: {value} kV',
            )
        if name in ('capillary_temp',) and value > 450:
            alert_service.create_alert(
                db,
                instrument_id=str(instrument.id),
                category='temperature_deviation',
                severity='warning',
                message=f'Capillary temperature high: {value} C',
            )
