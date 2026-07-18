from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app import models
from app.security import get_client_ip


def log_event(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_agent_id: Optional[str] = None,
    request=None,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    success: bool = True,
    error_code: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> models.AuditEvent:
    event = models.AuditEvent(
        actor_user_id=UUID(actor_user_id) if actor_user_id else None,
        actor_agent_id=UUID(actor_agent_id) if actor_agent_id else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        timestamp=datetime.now(timezone.utc),
        source_ip=get_client_ip(request) if request else None,
        user_agent=request.headers.get('user-agent') if request else None,
        before=before,
        after=after,
        meta=metadata or {},
        success=success,
        error_code=error_code,
    )
    db.add(event)
    db.commit()
    return event
