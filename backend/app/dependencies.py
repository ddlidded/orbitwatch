from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_current_active_user, get_current_user, require_permission


def get_instrument_or_404(
    instrument_id: str,
    user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> models.Instrument:
    # In a multi-tenant model, enforce user-instrument scope here.
    inst = db.query(models.Instrument).filter(models.Instrument.id == instrument_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Instrument not found')
    return inst


def require_csrf(request: Request) -> None:
    from app.security import verify_csrf

    verify_csrf(request)
