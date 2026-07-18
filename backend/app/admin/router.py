from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import audit, models, schemas
from app.database import get_db
from app.security import hash_password, require_permission

router = APIRouter(prefix='/admin', tags=['admin'])


@router.get('/users', response_model=schemas.PaginatedResponse)
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('user:read')),
):
    total = db.query(models.User).count()
    items = db.query(models.User).offset(skip).limit(limit).all()
    return {
        'total': total,
        'page': skip // limit + 1,
        'page_size': limit,
        'items': [schemas.UserOut.model_validate(u) for u in items],
    }


@router.post('/users', response_model=schemas.UserOut)
def create_user(
    request,
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_permission('user:write')),
):
    existing = db.query(models.User).filter_by(email=str(data.email).lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already registered')
    user = models.User(
        email=str(data.email).lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        email_verified=True,
    )
    db.add(user)
    db.flush()
    for role_name in data.role_names or []:
        role = db.query(models.Role).filter_by(name=role_name).first()
        if role:
            db.add(models.UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    audit.log_event(
        db,
        'user_create',
        'user',
        resource_id=str(user.id),
        actor_user_id=str(admin_user.id),
        request=request,
        after={'email': user.email, 'roles': data.role_names},
    )
    return user


@router.patch('/users/{user_id}')
def update_user(
    user_id: str,
    data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_permission('user:write')),
):
    user = db.query(models.User).filter_by(id=UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role_names is not None:
        db.query(models.UserRole).filter_by(user_id=user.id).delete()
        for role_name in data.role_names:
            role = db.query(models.Role).filter_by(name=role_name).first()
            if role:
                db.add(models.UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    return user


@router.get('/agents', response_model=list[schemas.AgentOut])
def list_agents(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('agent:read')),
):
    items = db.query(models.InstrumentAgent).order_by(models.InstrumentAgent.installed_at.desc()).all()
    return [schemas.AgentOut.model_validate(a) for a in items]


@router.post('/agents/{agent_id}/revoke')
def revoke_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('agent:write')),
):
    agent = db.query(models.InstrumentAgent).filter_by(id=UUID(agent_id)).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Agent not found')
    agent.is_active = False
    for cred in agent.credentials:
        cred.revoked = True
        cred.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {'revoked': True}
