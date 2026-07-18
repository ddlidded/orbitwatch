from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import audit, models, schemas
from app.database import get_db
from app.security import generate_token, hash_password, hash_token, require_permission

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
    request: Request,
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


@router.get('/users/{user_id}', response_model=schemas.UserOut)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_permission('user:read')),
):
    user = db.query(models.User).filter_by(id=UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return user


@router.patch('/users/{user_id}', response_model=schemas.UserOut)
def update_user(
    request: Request,
    user_id: str,
    data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_permission('user:write')),
):
    user = db.query(models.User).filter_by(id=UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    if user.id == admin_user.id and data.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot disable your own account')
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
    audit.log_event(
        db,
        'user_update',
        'user',
        resource_id=str(user.id),
        actor_user_id=str(admin_user.id),
        request=request,
        after={'full_name': user.full_name, 'is_active': user.is_active, 'roles': data.role_names},
    )
    return user


@router.delete('/users/{user_id}')
def delete_user(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_permission('user:write')),
):
    user = db.query(models.User).filter_by(id=UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    if user.id == admin_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot delete your own account')
    user.email = f"deleted.{user.id}@example.com"
    user.is_active = False
    db.query(models.UserRole).filter_by(user_id=user.id).delete()
    db.query(models.UserSession).filter_by(user_id=user.id, revoked=False).update({'revoked': True})
    db.commit()
    audit.log_event(
        db,
        'user_delete',
        'user',
        resource_id=str(user.id),
        actor_user_id=str(admin_user.id),
        request=request,
    )
    return {'deleted': True}


@router.post('/users/{user_id}/reset-password')
def reset_user_password(
    request: Request,
    user_id: str,
    data: schemas.AdminPasswordReset,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_permission('user:write')),
):
    user = db.query(models.User).filter_by(id=UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    user.hashed_password = hash_password(data.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    db.query(models.UserSession).filter_by(user_id=user.id, revoked=False).update({'revoked': True})
    db.commit()
    audit.log_event(
        db,
        'password_reset',
        'user',
        resource_id=str(user.id),
        actor_user_id=str(admin_user.id),
        request=request,
    )
    return {'message': 'Password reset. The user must log in again.'}


@router.post('/instruments', response_model=schemas.AgentRegisterResponse)
def create_instrument_and_agent(
    request: Request,
    data: schemas.InstrumentCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_permission('instrument:write')),
):
    existing = db.query(models.Instrument).filter_by(serial_number=data.serial_number).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Instrument with this serial number already exists')
    inst = models.Instrument(
        name=data.name,
        serial_number=data.serial_number,
        model=data.model,
        api_version=data.api_version,
        tune_version=data.tune_version,
        iapi_version=data.iapi_version,
        status='pending',
    )
    db.add(inst)
    db.flush()
    agent = models.InstrumentAgent(
        instrument_id=inst.id,
        hostname='pending',
        agent_version='pending',
    )
    db.add(agent)
    db.flush()
    token = generate_token(48)
    db.add(
        models.AgentCredential(
            agent_id=agent.id,
            token_hash=hash_token(token),
            scopes=['agent:send'],
        )
    )
    db.commit()
    audit.log_event(
        db,
        'instrument_created',
        'instrument',
        resource_id=str(inst.id),
        actor_user_id=str(admin_user.id),
        request=request,
    )
    return {'agent_id': agent.id, 'instrument_id': inst.id, 'token': token}


@router.get('/roles', response_model=list[schemas.RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('user:read')),
):
    return db.query(models.Role).order_by(models.Role.name).all()


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
