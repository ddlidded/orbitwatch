from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.audit import log_event
from app.database import get_db
from app.security import get_current_active_user, require_permission
from app.services import target_service

router = APIRouter(prefix='/target-lists', tags=['target-lists'])


@router.post('/import', response_model=schemas.TargetListOut)
def import_target_list(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('target:write')),
):
    content = file.file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='File too large')
    target_list = target_service.create_target_list_version(
        db, str(user.id), name, description, content, file.filename
    )
    log_event(
        db,
        'target-list_upload',
        'target_list',
        resource_id=str(target_list.id),
        actor_user_id=str(user.id),
        request=request,
        after={'name': name, 'version_id': str(target_list.active_version_id)},
    )
    return target_list


@router.post('', response_model=schemas.TargetListOut)
def create_target_list(
    request: Request,
    data: schemas.TargetListCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('target:write')),
):
    name = data.name
    description = data.description
    # Minimal placeholder; full import uses /import.
    target_list = models.TargetList(name=name, description=description, owner_id=user.id)
    db.add(target_list)
    db.commit()
    log_event(
        db,
        'target-list_create',
        'target_list',
        resource_id=str(target_list.id),
        actor_user_id=str(user.id),
        request=request,
    )
    return target_list


@router.get('', response_model=list[schemas.TargetListOut])
def list_target_lists(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('target:read')),
):
    items = db.query(models.TargetList).order_by(models.TargetList.created_at.desc()).all()
    return [schemas.TargetListOut.model_validate(tl) for tl in items]


@router.get('/{target_list_id}', response_model=schemas.TargetListOut)
def get_target_list(
    target_list_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('target:read')),
):
    tl = db.query(models.TargetList).filter_by(id=UUID(target_list_id)).first()
    if not tl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Target list not found')
    return tl


@router.post('/{target_list_id}/activate')
def activate_target_list(
    target_list_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('target:write')),
):
    tl = db.query(models.TargetList).filter_by(id=UUID(target_list_id)).first()
    if not tl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Target list not found')
    version = db.query(models.TargetListVersion).filter_by(id=UUID(version_id)).first()
    if not version or version.target_list_id != tl.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid version')
    tl.active_version_id = version.id
    db.commit()
    return {'active_version_id': str(version.id)}


@router.post('/{target_list_id}/assign')
def assign_target_list_to_instrument(
    target_list_id: str,
    instrument_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('target:write')),
):
    tl = db.query(models.TargetList).filter_by(id=UUID(target_list_id)).first()
    if not tl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Target list not found')
    inst = db.query(models.Instrument).filter_by(id=UUID(instrument_id)).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Instrument not found')
    if not tl.active_version_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Target list has no active version')
    assignment = models.TargetAssignment(
        target_list_id=tl.id,
        instrument_id=inst.id,
        assigned_by_user_id=user.id,
    )
    db.add(assignment)
    db.commit()
    log_event(
        db,
        'target-list_assign',
        'target_assignment',
        resource_id=str(tl.id),
        actor_user_id=str(user.id),
        request=request,
        after={'instrument_id': str(inst.id), 'version_id': str(tl.active_version_id)},
    )
    return {'target_assignment_id': str(assignment.id)}
