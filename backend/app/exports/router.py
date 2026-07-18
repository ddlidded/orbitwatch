from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import require_permission
from app.services import export_service

router = APIRouter(prefix='/exports', tags=['exports'])


@router.post('', response_model=schemas.ExportJobOut)
def create_export(
    export_type: str,
    sample_id: str | None = None,
    sample_target_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('export:write')),
):
    if export_type == 'tic' and sample_id:
        key = export_service.export_tic_csv(db, sample_id)
    elif export_type == 'xic' and sample_target_id:
        key = export_service.export_xic_csv(db, sample_target_id)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported export')
    export = models.ExportJob(
        requested_by_user_id=UUID(str(user.id)),
        export_type=export_type,
        format='csv',
        file_key=key,
        status='completed',
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


@router.get('/{export_id}', response_model=schemas.ExportJobOut)
def get_export(
    export_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission('export:read')),
):
    export = db.query(models.ExportJob).filter_by(id=UUID(export_id)).first()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Export not found')
    return export
