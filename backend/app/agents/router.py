from __future__ import annotations

import hmac
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.database import get_db
from app.security import get_agent_from_token, hash_token
from app.services import ingestion

router = APIRouter(prefix='/agents', tags=['agents'])


def _get_agent(request: Request, db: Session = Depends(get_db)) -> models.InstrumentAgent:
    token = request.headers.get('x-agent-token')
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing agent token')
    agent = get_agent_from_token(token, db)
    if not agent or not agent.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid agent token')
    return agent


@router.post('/register', response_model=schemas.AgentRegisterResponse)
def register_agent(
    request: Request,
    data: schemas.AgentRegister,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    bootstrap_token = request.headers.get('x-agent-token') or ''
    expected = settings.agent_bootstrap_token
    if settings.orbitwatch_env == 'production' or expected:
        if not expected or not hmac.compare_digest(bootstrap_token, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Invalid or missing agent bootstrap token',
            )
    return ingestion.handle_agent_register(db, data.model_dump(), data.capabilities)


@router.post('/messages')
def receive_messages(
    request: Request,
    envelope: schemas.MessageEnvelope,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    # Optional body-size defense already enforced by FastAPI/Starlette.
    agent = _get_agent(request, db)
    if str(agent.id) != str(envelope.agentId):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Agent ID mismatch')
    if agent.instrument_id and str(agent.instrument_id) != str(envelope.instrumentId):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Instrument ID mismatch')
    if ingestion._dedup_message(db, str(agent.id), str(envelope.messageId), envelope.type):
        db.commit()
        return schemas.AgentMessageAck(acknowledged_message_ids=[envelope.messageId])

    payload = envelope.payload or {}
    if envelope.type == 'agent.heartbeat':
        ingestion.handle_agent_heartbeat(db, agent, payload)
    elif envelope.type == 'sequence.started':
        ingestion.handle_sequence_started(db, agent, payload)
    elif envelope.type == 'sample.started':
        ingestion.handle_sample_started(db, agent, payload)
    elif envelope.type == 'scan':
        ingestion.handle_scan(db, agent, envelope.model_dump(), payload)
    elif envelope.type == 'telemetry.batch':
        ingestion.handle_telemetry_batch(db, agent, payload)
    elif envelope.type == 'sample.completed':
        ingestion.handle_sample_completed(db, agent, payload)
    elif envelope.type == 'sample.failed':
        ingestion.handle_sample_failed(db, agent, payload)
    elif envelope.type == 'sequence.completed':
        ingestion.handle_sequence_completed(db, agent, payload)
    elif envelope.type == 'rawfile.available':
        ingestion.handle_rawfile_available(db, agent, payload)
    elif envelope.type in ('agent.warning', 'agent.error'):
        ingestion.handle_agent_warning(db, agent, payload)
    else:
        # Ack but ignore unknown types.
        pass

    db.commit()
    return schemas.AgentMessageAck(acknowledged_message_ids=[envelope.messageId])


@router.get('/instruments/{instrument_id}/samples/{external_sample_id}/targets')
def get_agent_targets(
    instrument_id: str,
    external_sample_id: str,
    db: Session = Depends(get_db),
    agent: models.InstrumentAgent = Depends(_get_agent),
):
    if agent.instrument_id and str(agent.instrument_id) != instrument_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Instrument not assigned to this agent')
    sample = (
        db.query(models.Sample)
        .join(models.Sequence)
        .filter(
            models.Sequence.instrument_id == UUID(instrument_id),
            models.Sample.external_sample_id == external_sample_id,
        )
        .first()
    )
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Sample not found')
    items = []
    for st in sample.sample_targets:
        items.append(
            {
                'sample_target_id': str(st.id),
                'target_id': str(st.target_id),
                'compound_name': st.target.compound_name,
                'target_mz': float(st.target.target_mz),
                'polarity': st.target.polarity,
                'tolerance_value': float(st.target.tolerance_value),
                'tolerance_unit': st.target.tolerance_unit,
                'expected_rt_minutes': (
                    float(st.target.expected_rt_minutes) if st.target.expected_rt_minutes else None
                ),
                'rt_window_minutes': float(st.target.rt_window_minutes),
            }
        )
    return items
