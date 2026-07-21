from __future__ import annotations

import logging
import secrets

from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import (
    AgentCapability,
    AlgorithmVersion,
    Instrument,
    InstrumentAgent,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.security import hash_password, verify_password

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_PERMISSIONS = [
    ('instrument', 'read'),
    ('instrument', 'write'),
    ('instrument', 'admin'),
    ('sequence', 'read'),
    ('sample', 'read'),
    ('target', 'read'),
    ('target', 'write'),
    ('alert', 'read'),
    ('alert', 'ack'),
    ('report', 'read'),
    ('report', 'write'),
    ('export', 'read'),
    ('export', 'write'),
    ('user', 'read'),
    ('user', 'write'),
    ('agent', 'read'),
    ('agent', 'write'),
    ('agent', 'admin'),
    ('settings', 'read'),
    ('settings', 'write'),
    ('audit', 'read'),
]

ROLE_PERMISSIONS = {
    'viewer': ['instrument:read', 'sequence:read', 'sample:read', 'target:read', 'alert:read', 'report:read', 'export:read'],
    'analyst': [
        'instrument:read', 'sequence:read', 'sample:read', 'target:read', 'target:write',
        'alert:read', 'alert:ack', 'report:read', 'report:write', 'export:read', 'export:write',
    ],
    'instrument_admin': [
        'instrument:read', 'instrument:write', 'sequence:read', 'sample:read', 'target:read', 'target:write',
        'alert:read', 'alert:ack', 'report:read', 'report:write', 'export:read', 'export:write',
        'agent:read', 'agent:write', 'settings:read',
    ],
    'system_admin': [f'{r}:{a}' for r, a in DEFAULT_PERMISSIONS],
}


def seed_database():
    from sqlalchemy import inspect

    if not inspect(engine).has_table('user'):
        from app.database import Base

        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Permissions
        perm_map = {}
        for resource, action in DEFAULT_PERMISSIONS:
            perm = db.query(Permission).filter_by(resource=resource, action=action).first()
            if not perm:
                perm = Permission(resource=resource, action=action)
                db.add(perm)
                db.flush()
            perm_map[f'{resource}:{action}'] = perm

        # Roles
        role_map = {}
        for role_name, perms in ROLE_PERMISSIONS.items():
            role = db.query(Role).filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name, description=f'{role_name} role')
                db.add(role)
                db.flush()
            role_map[role_name] = role
            # Assign permissions
            existing = {f'{rp.permission.resource}:{rp.permission.action}' for rp in role.role_permissions}
            for perm_name in perms:
                if perm_name not in existing:
                    db.add(RolePermission(role_id=role.id, permission_id=perm_map[perm_name].id))

        # Default admin
        admin = db.query(User).filter_by(email='admin@isotopiq.dev').first()
        if settings.admin_initial_password:
            admin_password = settings.admin_initial_password
        elif settings.orbitwatch_env == 'production':
            admin_password = secrets.token_urlsafe(24)
            logger.warning(
                'ORBITWATCH_ADMIN_PASSWORD not set. A one-time admin password has been generated: %s',
                admin_password,
            )
        else:
            admin_password = 'OrbitWatch-Admin-2024!'
            logger.warning(
                'Using default admin password. Set ORBITWATCH_ADMIN_PASSWORD in production.'
            )
        if not admin:
            admin = User(
                email='admin@isotopiq.dev',
                full_name='System Administrator',
                hashed_password=hash_password(admin_password),
                is_superuser=True,
                email_verified=True,
            )
            db.add(admin)
            db.flush()
            admin_role = role_map['system_admin']
            if not db.query(UserRole).filter_by(user_id=admin.id, role_id=admin_role.id).first():
                db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
        elif settings.admin_initial_password and not verify_password(settings.admin_initial_password, admin.hashed_password):
            admin.hashed_password = hash_password(admin_password)
            logger.warning(
                'ORBITWATCH_ADMIN_PASSWORD has changed; the admin password has been updated. '
                'Unset ORBITWATCH_ADMIN_PASSWORD after first boot if you do not want it to reset the admin password on every restart.'
            )

        # Default algorithm version
        if not db.query(AlgorithmVersion).filter_by(name='provisional_peak', version='1.0.0').first():
            db.add(AlgorithmVersion(name='provisional_peak', version='1.0.0', parameters={}))
        if not db.query(AlgorithmVersion).filter_by(name='final_peak', version='1.0.0').first():
            db.add(AlgorithmVersion(name='final_peak', version='1.0.0', parameters={}))

        db.commit()
        logger.info('Database seeded')
    except Exception:
        db.rollback()
        logger.exception('Seed failed')
        raise
    finally:
        db.close()


if __name__ == '__main__':
    seed_database()
