import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


def hash_password(plain: str) -> str:
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_auth_cookies(response, session_token: str, refresh_token: str) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    access_exp = now + timedelta(minutes=settings.access_token_ttl_minutes)
    refresh_exp = now + timedelta(days=settings.refresh_token_ttl_days)
    response.set_cookie(
        key='session',
        value=session_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        expires=access_exp,
        path='/',
    )
    response.set_cookie(
        key='refresh',
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        expires=refresh_exp,
        path='/api/v1/auth/refresh',
    )
    response.set_cookie(
        key='csrf_token',
        value=generate_token(16),
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        expires=access_exp,
        path='/',
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie('session', path='/')
    response.delete_cookie('refresh', path='/api/v1/auth/refresh')
    response.delete_cookie('csrf_token', path='/')


bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> models.User:
    token = request.cookies.get('session')
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    session = db.query(models.UserSession).filter_by(token=token, revoked=False).first()
    if not session or _ensure_utc(session.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session expired')
    if not session.user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User disabled')
    session.last_activity_at = datetime.now(timezone.utc)
    db.commit()
    return session.user


def get_current_active_user(user: models.User = Depends(get_current_user)) -> models.User:
    return user


def _collect_permissions(user: models.User) -> set[str]:
    perms: set[str] = set()
    for ur in user.user_roles:
        for rp in ur.role.role_permissions:
            perms.add(f"{rp.permission.resource}:{rp.permission.action}")
    return perms


def require_permission(permission: str):
    def checker(
        user: models.User = Depends(get_current_active_user),
    ) -> models.User:
        if user.is_superuser:
            return user
        perms = _collect_permissions(user)
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Missing permission {permission}',
            )
        return user

    return checker


def get_agent_from_token(token: str, db: Session) -> Optional[models.InstrumentAgent]:
    if not token:
        return None
    token_hash = hash_token(token)
    cred = (
        db.query(models.AgentCredential)
        .filter_by(token_hash=token_hash, revoked=False)
        .first()
    )
    if not cred:
        return None
    return cred.agent


def verify_csrf(request: Request) -> None:
    cookie = request.cookies.get('csrf_token')
    header = request.headers.get('x-csrf-token')
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='CSRF token mismatch')
