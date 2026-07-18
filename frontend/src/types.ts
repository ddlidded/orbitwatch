export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  email_verified: boolean;
  mfa_enabled: boolean;
  roles: string[];
}

export interface Instrument {
  id: string;
  name: string;
  serial_number: string;
  model: string;
  status: string;
  last_seen_at?: string;
}

export interface Sequence {
  id: string;
  instrument_id: string;
  name: string;
  external_sequence_id?: string;
  status: string;
  sample_count: number;
  started_at?: string;
  completed_at?: string;
}

export interface Sample {
  id: string;
  sequence_id: string;
  sample_name: string;
  sample_type?: string;
  method_name?: string;
  polarity?: string;
  acquisition_status: string;
  finalization_status: string;
  progress_pct: number;
  started_at?: string;
  completed_at?: string;
  position: number;
}

export interface TicPoint {
  retention_time_minutes: number;
  tic: number;
  scan_number?: number;
}

export interface DashboardSummary {
  current_sample?: Sample;
  current_sequence?: Sequence;
  run_time_min?: number;
  expected_run_time_min?: number;
  progress_pct: number;
  rt_live_min?: number;
  tic_live?: number;
  scan_number?: number;
  ms_order?: string;
  polarity?: string;
  instrument_status: string;
  alert_count: number;
  target_summary: Record<string, number>;
}

export interface AlertItem {
  id: string;
  category: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  first_seen_at: string;
  last_seen_at: string;
  status: string;
}

export interface PeakRow {
  compound_name: string;
  adduct?: string;
  target_mz: number;
  status: string;
  statusClass: string;
  rt?: number;
  expected_rt?: number;
  apex_intensity?: number;
  sn?: number;
  shape?: string;
  shapeClass?: string;
  filter: string;
  color?: string;
}

export interface Target {
  id: string;
  compound_name: string;
  formula?: string;
  adduct?: string;
  target_mz: number;
  polarity: string;
  expected_rt_minutes?: number;
  rt_window_minutes?: number;
  tolerance_value?: number;
  tolerance_unit?: string;
  enabled: boolean;
}

export interface SampleTarget {
  id: string;
  sample_id: string;
  target_id: string;
  state: string;
  target: Target;
}

export interface XicPoint {
  retention_time_minutes: number;
  intensity: number;
  observed_centroid_mz?: number;
  mass_error_ppm?: number;
}

export interface PeakMetric {
  id: string;
  detection_status: string;
  target_state?: string;
  observed_rt?: number;
  apex_intensity?: number;
  integrated_area?: number;
  signal_to_noise?: number;
  fwhm_minutes?: number;
  points_across_peak?: number;
  asymmetry_factor?: number;
  tailing_factor?: number;
  quality_class: string;
  quality_reasons: string[];
  provisional: boolean;
  calculated_at: string;
}

export interface TelemetryPoint {
  metric_name: string;
  metric_value: number;
  unit?: string;
  recorded_at: string;
}

export interface AgentInfo {
  id: string;
  hostname: string;
  agent_version: string;
  last_heartbeat_at?: string;
  is_active: boolean;
}

export interface TargetList {
  id: string;
  name: string;
  description?: string;
  archived: boolean;
  active_version_id?: string;
  created_at: string;
}
