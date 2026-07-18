from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app import audit, models, schemas
from app.config import get_settings
from app.database import get_db
from app.security import (
    clear_auth_cookies,
    generate_token,
    get_client_ip,
    get_current_active_user,
    get_current_user,
    hash_password,
    hash_token,
    set_auth_cookies,
    verify_password,
)

router = APIRouter(prefix='/auth', tags=['auth'])


@router.get('/csrf')
def get_csrf(request: Request, response: Response):
    # Returns nothing; the cookie is set by the client if missing.
    return {'ok': True}


@router.post('/login', response_model=schemas.UserOut)
def login(
    request: Request,
    response: Response,
    data: schemas.UserLogin,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(email=data.email.lower()).first()
    if not user or not user.hashed_password:
        # Generic response to avoid user enumeration.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account locked')
    if not verify_password(data.password, user.hashed_password):
        user.failed_login_count += 1
        if user.failed_login_count >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()
        audit.log_event(
            db,
            'login_failure',
            'user',
            resource_id=str(user.id),
            actor_user_id=str(user.id),
            request=request,
            success=False,
            error_code='INVALID_PASSWORD',
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')

    user.failed_login_count = 0
    user.locked_until = None
    db.flush()

    session_token = generate_token(32)
    refresh_token = generate_token(32)
    access_expires = datetime.now(timezone.utc) + timedelta(
        minutes=get_settings().access_token_ttl_minutes
    )
    db.add(
        models.UserSession(
            user_id=user.id,
            token=session_token,
            refresh_token=refresh_token,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get('user-agent'),
            expires_at=access_expires,
        )
    )
    db.commit()
    set_auth_cookies(response, session_token, refresh_token)
    audit.log_event(
        db,
        'login_success',
        'user',
        resource_id=str(user.id),
        actor_user_id=str(user.id),
        request=request,
    )
    return user


@router.post('/logout')
def logout(
    request: Request,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = request.cookies.get('session')
    if token:
        session = db.query(models.UserSession).filter_by(token=token).first()
        if session:
            session.revoked = True
            db.commit()
            audit.log_event(
                db,
                'logout',
                'user_session',
                resource_id=str(session.id),
                actor_user_id=str(user.id),
                request=request,
            )
    clear_auth_cookies(response)
    return {'ok': True}


@router.get('/me', response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_active_user)):
    return user


@router.post('/forgot-password')
def forgot_password(
    request: Request,
    data: schemas.PasswordResetRequest,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(email=data.email.lower()).first()
    if user:
        token = generate_token(32)
        db.add(
            models.PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
        )
        db.commit()
        # In production an email would be sent. We log only for audit.
        audit.log_event(
            db,
            'password_reset_request',
            'user',
            resource_id=str(user.id),
            actor_user_id=str(user.id),
            request=request,
        )
    # Generic response regardless of whether user exists.
    return {'message': 'If an account exists, a reset email has been sent.'}


@router.post('/reset-password')
def reset_password(
    request: Request,
    data: schemas.PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    token_hash = hash_token(data.token)
    prt = (
        db.query(models.PasswordResetToken)
        .filter_by(token_hash=token_hash, used=False)
        .first()
    )
    if not prt or prt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired token')
    user = prt.user
    user.hashed_password = hash_password(data.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    prt.used = True
    db.commit()
    audit.log_event(
        db,
        'password_reset',
        'user',
        resource_id=str(user.id),
        actor_user_id=str(user.id),
        request=request,
    )
    return {'message': 'Password updated'}


@router.post('/verify-email')
def verify_email(token: str, db: Session = Depends(get_db)):
    token_hash = hash_token(token)
    evt = (
        db.query(models.EmailVerificationToken)
        .filter_by(token_hash=token_hash, used=False)
        .first()
    )
    if not evt or evt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired token')
    evt.user.email_verified = True
    evt.used = True
    db.commit()
    return {'message': 'Email verified'}
