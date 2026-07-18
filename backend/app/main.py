from __future__ import annotations

import logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.admin.router import router as admin_router
from app.agents.router import router as agents_router
from app.alerts.router import router as alerts_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.dashboard.router import router as dashboard_router
from app.database import Base, engine
from app.exports.router import router as exports_router
from app.instruments.router import router as instruments_router
from app.realtime.manager import manager as realtime_manager
from app.reports.router import router as reports_router
from app.samples.router import router as samples_router
from app.sequences.router import router as sequences_router
from app.target_lists.router import router as target_lists_router
from app.security import get_current_active_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title='OrbitWatch',
    version=__version__,
    docs_url='/api/v1/docs',
    redoc_url='/api/v1/redoc',
    openapi_url='/api/v1/openapi.json',
)

settings = get_settings()

# CORS for development; restrict to exact origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception('Unhandled exception: %s', exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            'error': {
                'code': 'INTERNAL_SERVER_ERROR',
                'message': 'An unexpected error occurred.',
            }
        },
    )


@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine)
    from app.seed import seed_database

    seed_database()


app.include_router(auth_router, prefix='/api/v1')
app.include_router(instruments_router, prefix='/api/v1')
app.include_router(sequences_router, prefix='/api/v1')
app.include_router(samples_router, prefix='/api/v1')
app.include_router(target_lists_router, prefix='/api/v1')
app.include_router(alerts_router, prefix='/api/v1')
app.include_router(reports_router, prefix='/api/v1')
app.include_router(exports_router, prefix='/api/v1')
app.include_router(admin_router, prefix='/api/v1')
app.include_router(agents_router, prefix='/api/v1')
app.include_router(dashboard_router, prefix='/api/v1')


@app.get('/healthz')
def health():
    return {'status': 'ok', 'version': __version__}


@app.get('/ready')
def ready():
    return {'status': 'ready'}


@app.websocket('/ws/live')
async def websocket_endpoint(websocket: WebSocket):
    # Extract session cookie for authentication.
    user = None
    try:
        from app.database import SessionLocal
        from app.security import get_current_active_user as _get_user

        # Manual cookie authentication for WebSocket.
        # Synchronous user resolution is not awaitable; resolve in thread.
        import asyncio

        def resolve_user():
            from datetime import datetime, timezone
            from sqlalchemy.orm import joinedload

            db = SessionLocal()
            try:
                token = websocket.cookies.get('session')
                if not token:
                    return None
                from app import models

                def _ensure_utc(value):
                    if value.tzinfo is None:
                        return value.replace(tzinfo=timezone.utc)
                    return value

                session = (
                    db.query(models.UserSession)
                    .options(
                        joinedload(models.UserSession.user)
                        .joinedload(models.User.user_roles)
                        .joinedload(models.UserRole.role)
                    )
                    .filter_by(token=token, revoked=False)
                    .first()
                )
                if not session or _ensure_utc(session.expires_at) < datetime.now(timezone.utc):
                    return None
                return session.user
            finally:
                db.close()

        user = await asyncio.to_thread(resolve_user)
    except Exception:
        user = None

    if not user:
        await websocket.close(code=1008)
        return

    roles = {r for r in user.roles}
    # For demo, allow all instrument channels. Later filter by UserInstrument.
    def _all_instrument_ids():
        db = SessionLocal()
        try:
            return {str(i.id) for i in db.query(models.Instrument.id).all()}
        finally:
            db.close()

    instruments = await asyncio.to_thread(_all_instrument_ids)
    conn_id = await realtime_manager.connect(websocket, str(user.id), roles, instruments)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg.startswith('subscribe:'):
                channel = msg[len('subscribe:') :]
                realtime_manager.subscribe(conn_id, channel)
            elif msg.startswith('unsubscribe:'):
                channel = msg[len('unsubscribe:') :]
                realtime_manager.unsubscribe(conn_id, channel)
    except WebSocketDisconnect:
        realtime_manager.disconnect(conn_id)
