import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = 'user'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[List['UserSession']] = relationship(
        'UserSession', back_populates='user', cascade='all, delete-orphan'
    )
    user_roles: Mapped[List['UserRole']] = relationship(
        'UserRole', back_populates='user', cascade='all, delete-orphan'
    )
    owned_target_lists: Mapped[List['TargetList']] = relationship(
        'TargetList', back_populates='owner'
    )
    audit_events: Mapped[List['AuditEvent']] = relationship('AuditEvent', back_populates='user')
    alert_acks: Mapped[List['AlertAcknowledgment']] = relationship(
        'AlertAcknowledgment', back_populates='acknowledged_by_user'
    )
    reports: Mapped[List['Report']] = relationship('Report', back_populates='requested_by_user')
    exports: Mapped[List['ExportJob']] = relationship('ExportJob', back_populates='requested_by_user')
    settings: Mapped[List['UserSetting']] = relationship(
        'UserSetting', back_populates='user', cascade='all, delete-orphan'
    )

    @property
    def roles(self) -> List[str]:
        return [ur.role.name for ur in self.user_roles]


class Role(Base):
    __tablename__ = 'role'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_roles: Mapped[List['UserRole']] = relationship(
        'UserRole', back_populates='role', cascade='all, delete-orphan'
    )
    role_permissions: Mapped[List['RolePermission']] = relationship(
        'RolePermission', back_populates='role', cascade='all, delete-orphan'
    )

    @property
    def permissions(self) -> List[str]:
        return [f'{rp.permission.resource}:{rp.permission.action}' for rp in self.role_permissions]


class Permission(Base):
    __tablename__ = 'permission'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    role_permissions: Mapped[List['RolePermission']] = relationship(
        'RolePermission', back_populates='permission', cascade='all, delete-orphan'
    )

    __table_args__ = (UniqueConstraint('resource', 'action'),)


class UserRole(Base):
    __tablename__ = 'user_role'

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('user.id'), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('role.id'), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped['User'] = relationship('User', back_populates='user_roles')
    role: Mapped['Role'] = relationship('Role', back_populates='user_roles')


class RolePermission(Base):
    __tablename__ = 'role_permission'

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('role.id'), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('permission.id'), primary_key=True
    )

    role: Mapped['Role'] = relationship('Role', back_populates='role_permissions')
    permission: Mapped['Permission'] = relationship('Permission', back_populates='role_permissions')


class UserSession(Base):
    __tablename__ = 'user_session'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    refresh_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped['User'] = relationship('User', back_populates='sessions')

    __table_args__ = (Index('idx_session_user_token', 'user_id', 'token'),)


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_token'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailVerificationToken(Base):
    __tablename__ = 'email_verification_token'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Instrument(Base):
    __tablename__ = 'instrument'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    serial_number: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    model: Mapped[str] = mapped_column(String(255))
    api_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tune_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    iapi_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    agent_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='offline')
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agents: Mapped[List['InstrumentAgent']] = relationship(
        'InstrumentAgent', back_populates='instrument', cascade='all, delete-orphan'
    )
    sequences: Mapped[List['Sequence']] = relationship('Sequence', back_populates='instrument')
    telemetry: Mapped[List['InstrumentTelemetry']] = relationship(
        'InstrumentTelemetry', back_populates='instrument'
    )
    alerts: Mapped[List['Alert']] = relationship('Alert', back_populates='instrument')
    target_assignments: Mapped[List['TargetAssignment']] = relationship(
        'TargetAssignment', back_populates='instrument'
    )


class IngestedMessage(Base):
    __tablename__ = 'ingested_message'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('instrument_agent.id'))
    message_type: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InstrumentAgent(Base):
    __tablename__ = 'instrument_agent'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('instrument.id'), nullable=True
    )
    hostname: Mapped[str] = mapped_column(String(255))
    agent_version: Mapped[str] = mapped_column(String(64))
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict] = mapped_column('metadata', JSON, default=dict)

    instrument: Mapped[Optional['Instrument']] = relationship(
        'Instrument', back_populates='agents'
    )
    credentials: Mapped[List['AgentCredential']] = relationship(
        'AgentCredential', back_populates='agent', cascade='all, delete-orphan'
    )
    capabilities: Mapped[List['AgentCapability']] = relationship(
        'AgentCapability', back_populates='agent', cascade='all, delete-orphan'
    )
    audit_events: Mapped[List['AuditEvent']] = relationship('AuditEvent', back_populates='agent')


class AgentCredential(Base):
    __tablename__ = 'agent_credential'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('instrument_agent.id'))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    scopes: Mapped[List[str]] = mapped_column(JSON, default=list)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    agent: Mapped['InstrumentAgent'] = relationship('InstrumentAgent', back_populates='credentials')


class AgentCapability(Base):
    __tablename__ = 'agent_capability'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('instrument_agent.id'))
    capability_key: Mapped[str] = mapped_column(String(64))
    capability_value: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped['InstrumentAgent'] = relationship('InstrumentAgent', back_populates='capabilities')

    __table_args__ = (UniqueConstraint('agent_id', 'capability_key'),)


class Sequence(Base):
    __tablename__ = 'sequence'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('instrument.id'))
    external_sequence_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(512))
    source_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='running')
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instrument: Mapped['Instrument'] = relationship('Instrument', back_populates='sequences')
    samples: Mapped[List['Sample']] = relationship('Sample', back_populates='sequence')

    __table_args__ = (
        Index('idx_sequence_instrument_started', 'instrument_id', 'started_at'),
    )


class Sample(Base):
    __tablename__ = 'sample'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('sequence.id'))
    external_sample_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    sample_name: Mapped[str] = mapped_column(String(512))
    sample_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    method_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    polarity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    vial_position: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_file_name: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    expected_runtime_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acquisition_status: Mapped[str] = mapped_column(String(32), default='queued')
    finalization_status: Mapped[str] = mapped_column(String(32), default='pending')
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sequence: Mapped['Sequence'] = relationship('Sequence', back_populates='samples')
    scans: Mapped[List['Scan']] = relationship('Scan', back_populates='sample')
    tic_points: Mapped[List['TicPoint']] = relationship('TicPoint', back_populates='sample')
    sample_targets: Mapped[List['SampleTarget']] = relationship(
        'SampleTarget', back_populates='sample', cascade='all, delete-orphan'
    )
    telemetry: Mapped[List['InstrumentTelemetry']] = relationship('InstrumentTelemetry', back_populates='sample')
    alerts: Mapped[List['Alert']] = relationship('Alert', back_populates='sample')

    __table_args__ = (
        Index('idx_sample_sequence_position', 'sequence_id', 'position'),
        Index('idx_sample_status', 'acquisition_status'),
    )


class AcquisitionMethod(Base):
    __tablename__ = 'acquisition_method'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('instrument.id'))
    name: Mapped[str] = mapped_column(String(255))
    method_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    method_definition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    instrument: Mapped['Instrument'] = relationship('Instrument')


class Scan(Base):
    __tablename__ = 'scan'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('sample.id'))
    agent_scan_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scan_number: Mapped[int] = mapped_column(Integer)
    retention_time_minutes: Mapped[float] = mapped_column(Numeric(12, 6))
    acquired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ms_order: Mapped[int] = mapped_column(Integer, default=1)
    polarity: Mapped[str] = mapped_column(String(16))
    scan_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tic: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    tic_source: Mapped[str] = mapped_column(String(32), default='unknown')
    base_peak_mz: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    base_peak_intensity: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    low_mz: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    high_mz: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    ingestion_sequence_number: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sample: Mapped['Sample'] = relationship('Sample', back_populates='scans')
    tic_points: Mapped[List['TicPoint']] = relationship('TicPoint', back_populates='scan')
    xic_points: Mapped[List['XicPoint']] = relationship('XicPoint', back_populates='scan')

    __table_args__ = (
        UniqueConstraint('sample_id', 'scan_number', 'agent_scan_id', name='uix_scan_sample_scan_number'),
        Index('idx_scan_sample_rt', 'sample_id', 'retention_time_minutes'),
    )


class TicPoint(Base):
    __tablename__ = 'tic_point'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('sample.id'))
    scan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('scan.id'))
    retention_time_minutes: Mapped[float] = mapped_column(Numeric(12, 6))
    tic: Mapped[float] = mapped_column(Numeric(18, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sample: Mapped['Sample'] = relationship('Sample', back_populates='tic_points')
    scan: Mapped['Scan'] = relationship('Scan', back_populates='tic_points')

    __table_args__ = (
        UniqueConstraint('sample_id', 'scan_id'),
        Index('idx_tic_point_sample_rt', 'sample_id', 'retention_time_minutes'),
    )


class TargetList(Base):
    __tablename__ = 'target_list'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    active_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('target_list_version.id'), nullable=True
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped['User'] = relationship('User', back_populates='owned_target_lists')
    versions: Mapped[List['TargetListVersion']] = relationship(
        'TargetListVersion',
        back_populates='target_list',
        foreign_keys='TargetListVersion.target_list_id',
    )
    active_version: Mapped[Optional['TargetListVersion']] = relationship(
        'TargetListVersion', foreign_keys=[active_version_id]
    )
    assignments: Mapped[List['TargetAssignment']] = relationship(
        'TargetAssignment', back_populates='target_list'
    )


class TargetListVersion(Base):
    __tablename__ = 'target_list_version'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_list_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('target_list.id'))
    version_number: Mapped[int] = mapped_column(Integer)
    uploaded_file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    uploaded_file_checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    target_list: Mapped['TargetList'] = relationship(
        'TargetList',
        back_populates='versions',
        foreign_keys=[target_list_id],
    )
    targets: Mapped[List['Target']] = relationship('Target', back_populates='target_list_version')
    uploaded_by_user: Mapped['User'] = relationship('User')

    __table_args__ = (UniqueConstraint('target_list_id', 'version_number'),)


class Target(Base):
    __tablename__ = 'target'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_list_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('target_list_version.id')
    )
    compound_name: Mapped[str] = mapped_column(String(255))
    formula: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    adduct: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_mz: Mapped[float] = mapped_column(Numeric(18, 8))
    mz_source: Mapped[str] = mapped_column(String(32), default='user')
    polarity: Mapped[str] = mapped_column(String(16))
    expected_rt_minutes: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    rt_window_minutes: Mapped[float] = mapped_column(Numeric(10, 4), default=0.5)
    tolerance_value: Mapped[float] = mapped_column(Numeric(12, 6), default=5.0)
    tolerance_unit: Mapped[str] = mapped_column(String(16), default='ppm')
    minimum_signal_to_noise: Mapped[float] = mapped_column(Numeric(10, 4), default=3.0)
    minimum_points_across_peak: Mapped[int] = mapped_column(Integer, default=7)
    maximum_fwhm_minutes: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict] = mapped_column('metadata', JSON, default=dict)

    target_list_version: Mapped['TargetListVersion'] = relationship(
        'TargetListVersion', back_populates='targets'
    )
    sample_targets: Mapped[List['SampleTarget']] = relationship('SampleTarget', back_populates='target')


class TargetAssignment(Base):
    __tablename__ = 'target_assignment'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_list_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('target_list.id'))
    instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('instrument.id'), nullable=True
    )
    method_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('acquisition_method.id'), nullable=True
    )
    sequence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('sequence.id'), nullable=True
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    target_list: Mapped['TargetList'] = relationship('TargetList', back_populates='assignments')
    instrument: Mapped[Optional['Instrument']] = relationship('Instrument', back_populates='target_assignments')
    method: Mapped[Optional['AcquisitionMethod']] = relationship('AcquisitionMethod')
    sequence: Mapped[Optional['Sequence']] = relationship('Sequence')


class SampleTarget(Base):
    __tablename__ = 'sample_target'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('sample.id'))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('target.id'))
    state: Mapped[str] = mapped_column(String(32), default='waiting')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sample: Mapped['Sample'] = relationship('Sample', back_populates='sample_targets')
    target: Mapped['Target'] = relationship('Target', back_populates='sample_targets')
    xic_points: Mapped[List['XicPoint']] = relationship(
        'XicPoint', back_populates='sample_target', cascade='all, delete-orphan'
    )
    peak_metrics: Mapped[List['PeakMetric']] = relationship('PeakMetric', back_populates='sample_target')

    __table_args__ = (UniqueConstraint('sample_id', 'target_id'),)


class XicPoint(Base):
    __tablename__ = 'xic_point'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sample_target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('sample_target.id')
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('scan.id'))
    retention_time_minutes: Mapped[float] = mapped_column(Numeric(12, 6))
    intensity: Mapped[float] = mapped_column(Numeric(18, 6))
    observed_centroid_mz: Mapped[Optional[float]] = mapped_column(Numeric(18, 8), nullable=True)
    mass_error_ppm: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sample_target: Mapped['SampleTarget'] = relationship('SampleTarget', back_populates='xic_points')
    scan: Mapped['Scan'] = relationship('Scan', back_populates='xic_points')

    __table_args__ = (
        UniqueConstraint('sample_target_id', 'scan_id'),
        Index('idx_xic_point_sample_target_rt', 'sample_target_id', 'retention_time_minutes'),
    )


class PeakMetric(Base):
    __tablename__ = 'peak_metric'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sample_target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('sample_target.id')
    )
    algorithm_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('algorithm_version.id')
    )
    provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    detection_status: Mapped[str] = mapped_column(String(32), default='not_detected')
    target_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    observed_rt: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    apex_intensity: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    integrated_area: Mapped[Optional[float]] = mapped_column(Numeric(24, 6), nullable=True)
    mass_error_ppm: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    signal_to_noise: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    fwhm_minutes: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    points_across_peak: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    asymmetry_factor: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    tailing_factor: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    baseline_estimate: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    integration_start_rt: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    integration_end_rt: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    quality_class: Mapped[str] = mapped_column(String(16), default='unknown')
    quality_reasons: Mapped[List[str]] = mapped_column(JSON, default=list)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sample_target: Mapped['SampleTarget'] = relationship('SampleTarget', back_populates='peak_metrics')
    algorithm_version: Mapped['AlgorithmVersion'] = relationship('AlgorithmVersion')

    __table_args__ = (
        UniqueConstraint('sample_target_id', 'algorithm_version_id', 'provisional'),
    )


class InstrumentTelemetry(Base):
    __tablename__ = 'instrument_telemetry'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('instrument.id'))
    sample_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('sample.id'), nullable=True
    )
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    metric_value: Mapped[float] = mapped_column(Numeric(18, 8))
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    instrument: Mapped['Instrument'] = relationship('Instrument', back_populates='telemetry')
    sample: Mapped[Optional['Sample']] = relationship('Sample', back_populates='telemetry')

    __table_args__ = (
        Index('idx_telemetry_instrument_recorded', 'instrument_id', 'recorded_at'),
    )


class AlertRule(Base):
    __tablename__ = 'alert_rule'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('instrument.id'), nullable=True
    )
    category: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default='warning')
    threshold: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Alert(Base):
    __tablename__ = 'alert'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('instrument.id'))
    sequence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('sequence.id'), nullable=True
    )
    sample_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('sample.id'), nullable=True
    )
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('target.id'), nullable=True
    )
    category: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default='open')
    acknowledged_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('user.id'), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column('metadata', JSON, default=dict)

    instrument: Mapped['Instrument'] = relationship('Instrument', back_populates='alerts')
    sequence: Mapped[Optional['Sequence']] = relationship('Sequence')
    sample: Mapped[Optional['Sample']] = relationship('Sample', back_populates='alerts')
    target: Mapped[Optional['Target']] = relationship('Target')
    acknowledgments: Mapped[List['AlertAcknowledgment']] = relationship(
        'AlertAcknowledgment', back_populates='alert', cascade='all, delete-orphan'
    )

    __table_args__ = (
        Index('idx_alert_status_severity', 'status', 'severity'),
    )


class AlertAcknowledgment(Base):
    __tablename__ = 'alert_acknowledgment'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('alert.id'))
    acknowledged_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('user.id')
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alert: Mapped['Alert'] = relationship('Alert', back_populates='acknowledgments')
    acknowledged_by_user: Mapped['User'] = relationship('User', back_populates='alert_acks')


class Report(Base):
    __tablename__ = 'report'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_type: Mapped[str] = mapped_column(String(64))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    file_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    requested_by_user: Mapped['User'] = relationship('User', back_populates='reports')


class ExportJob(Base):
    __tablename__ = 'export_job'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    export_type: Mapped[str] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(16))
    file_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    requested_by_user: Mapped['User'] = relationship('User', back_populates='exports')


class AuditEvent(Base):
    __tablename__ = 'audit_event'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('user.id'), nullable=True
    )
    actor_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('instrument_agent.id'), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    meta: Mapped[dict] = mapped_column('metadata', JSON, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    user: Mapped[Optional['User']] = relationship('User', back_populates='audit_events')
    agent: Mapped[Optional['InstrumentAgent']] = relationship(
        'InstrumentAgent', back_populates='audit_events'
    )

    __table_args__ = (
        Index('idx_audit_timestamp', 'timestamp'),
    )


class AlgorithmVersion(Base):
    __tablename__ = 'algorithm_version'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('name', 'version'),)


class SystemSetting(Base):
    __tablename__ = 'system_setting'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserSetting(Base):
    __tablename__ = 'user_setting'

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('user.id'))
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped['User'] = relationship('User', back_populates='settings')

    __table_args__ = (UniqueConstraint('user_id', 'key'),)
