import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = []
    correlation_id: Optional[str] = None


class UserBase(BaseModel):
    email: str
    full_name: str


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(..., min_length=12)
    role_names: list[str] = []


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role_names: Optional[list[str]] = None


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=12)
    new_password: str = Field(..., min_length=12)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    email_verified: bool
    mfa_enabled: bool
    roles: list[str] = []
    created_at: datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=12)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=12)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: list[str] = []


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    serial_number: str
    model: str
    api_version: Optional[str] = None
    tune_version: Optional[str] = None
    iapi_version: Optional[str] = None
    agent_version: Optional[str] = None
    status: str


class InstrumentCreate(BaseModel):
    name: str
    serial_number: str
    model: str = 'Orbitrap Exploris 480'
    api_version: Optional[str] = None
    tune_version: Optional[str] = None
    iapi_version: Optional[str] = None


class InstrumentTelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    metric_name: str
    metric_value: float
    unit: Optional[str] = None
    recorded_at: datetime


class SequenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    instrument_id: uuid.UUID
    external_sequence_id: Optional[str] = None
    name: str
    source_path: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    sample_count: int
    created_at: datetime


class SampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sequence_id: uuid.UUID
    external_sample_id: Optional[str] = None
    position: int
    sample_name: str
    sample_type: Optional[str] = None
    method_name: Optional[str] = None
    polarity: Optional[str] = None
    vial_position: Optional[str] = None
    raw_file_name: Optional[str] = None
    expected_runtime_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    acquisition_status: str
    finalization_status: str
    created_at: datetime

    @computed_field
    @property
    def progress_pct(self) -> int:
        if self.acquisition_status == 'completed':
            return 100
        if not self.started_at or not self.expected_runtime_seconds:
            return 0
        started = self.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return min(100, max(0, int(elapsed / self.expected_runtime_seconds * 100)))


class TicPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    retention_time_minutes: float
    tic: float
    scan_number: Optional[int] = None


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    compound_name: str
    formula: Optional[str] = None
    adduct: Optional[str] = None
    target_mz: float
    mz_source: str
    polarity: str
    expected_rt_minutes: Optional[float] = None
    rt_window_minutes: float
    tolerance_value: float
    tolerance_unit: str
    enabled: bool


class TargetListVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version_number: int
    uploaded_file_checksum: Optional[str] = None
    created_at: datetime


class TargetListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    archived: bool
    active_version_id: Optional[uuid.UUID] = None
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TargetListImportPreview(BaseModel):
    original_row: int
    compound_name: Optional[str] = None
    formula: Optional[str] = None
    adduct: Optional[str] = None
    target_mz: Optional[float] = None
    calculated_mz: Optional[float] = None
    polarity: Optional[str] = None
    expected_rt_minutes: Optional[float] = None
    warnings: list[str] = []
    errors: list[str] = []
    duplicate_status: str = 'unique'


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    instrument_id: uuid.UUID
    sequence_id: Optional[uuid.UUID] = None
    sample_id: Optional[uuid.UUID] = None
    target_id: Optional[uuid.UUID] = None
    category: str
    severity: str
    message: str
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int
    status: str
    acknowledged_by_user_id: Optional[uuid.UUID] = None
    acknowledged_at: Optional[datetime] = None
    notes: Optional[str] = None


class AlertAcknowledge(BaseModel):
    notes: Optional[str] = None


class NotificationOut(BaseModel):
    count: int
    items: list[AlertOut]


class SampleTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sample_id: uuid.UUID
    target_id: uuid.UUID
    state: str
    target: TargetOut


class XicPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sample_target_id: uuid.UUID
    scan_id: uuid.UUID
    retention_time_minutes: float
    intensity: float
    observed_centroid_mz: Optional[float] = None
    mass_error_ppm: Optional[float] = None
    provisional: bool
    created_at: datetime


class PeakMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sample_target_id: uuid.UUID
    algorithm_version_id: uuid.UUID
    provisional: bool
    detection_status: str
    target_state: Optional[str] = None
    observed_rt: Optional[float] = None
    apex_intensity: Optional[float] = None
    integrated_area: Optional[float] = None
    mass_error_ppm: Optional[float] = None
    signal_to_noise: Optional[float] = None
    fwhm_minutes: Optional[float] = None
    points_across_peak: Optional[int] = None
    asymmetry_factor: Optional[float] = None
    tailing_factor: Optional[float] = None
    baseline_estimate: Optional[float] = None
    integration_start_rt: Optional[float] = None
    integration_end_rt: Optional[float] = None
    quality_class: str
    quality_reasons: list[str] = []
    calculated_at: datetime


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    instrument_id: Optional[uuid.UUID] = None
    hostname: str
    agent_version: str
    installed_at: datetime
    last_heartbeat_at: Optional[datetime] = None
    is_active: bool


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    report_type: str
    status: str
    file_key: Optional[str] = None
    requested_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    parameters: dict = Field(default_factory=dict, exclude=True)

    @computed_field
    @property
    def sample_id(self) -> Optional[uuid.UUID]:
        return _uuid_from_params(self.parameters, 'sample_id')

    @computed_field
    @property
    def sequence_id(self) -> Optional[uuid.UUID]:
        return _uuid_from_params(self.parameters, 'sequence_id')


class ExportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    export_type: str
    format: str
    file_key: Optional[str] = None
    status: str
    requested_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


class AgentRegister(BaseModel):
    hostname: str
    agent_version: str
    instrument_serial: str
    instrument_name: str
    model: str = 'Orbitrap Exploris 480'
    api_version: Optional[str] = None
    tune_version: Optional[str] = None
    iapi_version: Optional[str] = None
    capabilities: dict[str, bool] = {}


class AgentRegisterResponse(BaseModel):
    agent_id: uuid.UUID
    instrument_id: uuid.UUID
    token: str


class MessageEnvelope(BaseModel):
    model_config = ConfigDict(extra='allow')
    schemaVersion: str = '1.0'
    messageId: uuid.UUID
    agentId: uuid.UUID
    instrumentId: uuid.UUID
    sequenceNumber: int
    sentAt: datetime
    type: str
    payload: dict[str, Any]

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {
            'agent.register', 'agent.heartbeat', 'agent.capabilities', 'agent.warning', 'agent.error',
            'instrument.identity', 'instrument.state', 'sequence.snapshot', 'sequence.started',
            'sequence.updated', 'sequence.completed', 'sample.started', 'sample.updated',
            'sample.completed', 'sample.failed', 'scan', 'tic.batch', 'xic.batch',
            'telemetry.batch', 'rawfile.available', 'processing.completed',
        }
        if v not in allowed:
            raise ValueError(f'Invalid message type: {v}')
        return v


class AgentMessageAck(BaseModel):
    acknowledged_message_ids: list[uuid.UUID]


class DashboardSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    current_sample: Optional[SampleOut] = None
    current_sequence: Optional[SequenceOut] = None
    run_time_min: Optional[float] = None
    expected_run_time_min: Optional[float] = None
    progress_pct: int = 0
    rt_live_min: Optional[float] = None
    tic_live: Optional[float] = None
    scan_number: Optional[int] = None
    ms_order: Optional[str] = None
    polarity: Optional[str] = None
    instrument_status: str = 'offline'
    alert_count: int = 0
    target_summary: dict[str, int] = {}


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Any]


def _uuid_from_params(params: dict, key: str) -> Optional[uuid.UUID]:
    value = params.get(key) if params else None
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
