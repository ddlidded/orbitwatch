from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import require_permission
from app.services import sequence_service

router = APIRouter(prefix='/sequences', tags=['sequences'])


@router.get('', response_model=schemas.PaginatedResponse)
def list_sequences(
    instrument_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sequence:read')),
):
    total, items = sequence_service.list_sequences(db, instrument_id, skip, limit)
    return {
        'total': total,
        'page': skip // limit + 1,
        'page_size': limit,
        'items': [schemas.SequenceOut.model_validate(s) for s in items],
    }


@router.get('/{sequence_id}', response_model=schemas.SequenceOut)
def get_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sequence:read')),
):
    seq = sequence_service.get_sequence(db, sequence_id)
    if not seq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Sequence not found')
    return seq


@router.get('/{sequence_id}/samples', response_model=schemas.PaginatedResponse)
def get_samples(
    sequence_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('sample:read')),
):
    total, items = sequence_service.list_samples(db, sequence_id, skip, limit)
    return {
        'total': total,
        'page': skip // limit + 1,
        'page_size': limit,
        'items': [schemas.SampleOut.model_validate(s) for s in items],
    }
