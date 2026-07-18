from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import find_peaks, savgol_filter

from app import models
from app.processing.xic import _mz_window


@dataclass
class PeakResult:
    detection_status: str = 'not_detected'
    target_state: str = 'waiting'
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
    quality_class: str = 'unknown'
    quality_reasons: list[str] = None

    def __post_init__(self):
        if self.quality_reasons is None:
            self.quality_reasons = []


def _estimate_baseline(intensity: np.ndarray) -> float:
    if intensity.size == 0:
        return 0.0
    return float(np.percentile(intensity, 20))


def _estimate_noise(intensity: np.ndarray, baseline: float) -> float:
    residuals = intensity - baseline
    if residuals.size < 2:
        return 1.0
    # Use the lower half of residuals (background-only) to avoid inflating noise with the peak.
    half_threshold = np.percentile(residuals, 50)
    background = residuals[residuals <= half_threshold]
    if background.size < 2:
        background = residuals
    return max(float(np.std(background)), 1e-12)


def _smooth(intensity: np.ndarray) -> np.ndarray:
    n = intensity.size
    if n < 7:
        return intensity
    window = min(7 if n % 2 == 1 else 8, n - 1)
    if window < 5:
        return intensity
    window = window if window % 2 == 1 else window - 1
    try:
        return savgol_filter(intensity, window, 2)
    except Exception:
        return intensity


def detect_peak(
    rt_array: list[float],
    intensity_array: list[float],
    target: models.Target,
    algorithm_version: models.AlgorithmVersion,
    provisional: bool = True,
) -> PeakResult:
    result = PeakResult()
    result.mass_error_ppm = None

    if not rt_array or not intensity_array or len(rt_array) < 3:
        result.quality_reasons.append('insufficient_scans')
        return result

    rt = np.asarray(rt_array, dtype=np.float64)
    intensity = np.asarray(intensity_array, dtype=np.float64)
    expected_rt = float(target.expected_rt_minutes) if target.expected_rt_minutes is not None else None
    rt_window = float(target.rt_window_minutes) if target.rt_window_minutes is not None else 0.5

    if expected_rt is not None:
        window_mask = (rt >= expected_rt - rt_window) & (rt <= expected_rt + rt_window)
        if window_mask.sum() == 0:
            result.target_state = 'outside_window'
            result.quality_reasons.append('outside_rt_window')
            return result
        rt_windowed = rt[window_mask]
        intensity_windowed = intensity[window_mask]
    else:
        rt_windowed = rt
        intensity_windowed = intensity

    baseline = _estimate_baseline(intensity_windowed)
    noise = _estimate_noise(intensity_windowed, baseline)
    result.baseline_estimate = baseline

    corrected = intensity_windowed - baseline
    smoothed = _smooth(corrected)

    if corrected.max() <= 0:
        result.target_state = 'not_detected'
        result.quality_reasons.append('low_signal')
        return result

    prominence = max(noise * 3.0, corrected.max() * 0.05)
    peaks, properties = find_peaks(
        smoothed,
        prominence=prominence,
        height=noise * 3.0,
        distance=1,
    )

    if peaks.size == 0:
        result.target_state = 'not_detected'
        result.quality_reasons.append('not_detected')
        return result

    # Select peak closest to expected RT if available, else the most intense.
    if expected_rt is not None:
        idx = int(peaks[np.argmin(np.abs(rt_windowed[peaks] - expected_rt))])
    else:
        idx = int(peaks[np.argmax(smoothed[peaks])])

    apex_intensity = float(corrected[idx])
    apex_rt = float(rt_windowed[idx])

    # Integration boundaries by walking down to baseline.
    left_bases = properties.get('left_bases')
    right_bases = properties.get('right_bases')
    if left_bases is not None and right_bases is not None and len(left_bases) > 0:
        peak_index_in_properties = int(np.where(peaks == idx)[0][0])
        left_idx = int(left_bases[peak_index_in_properties])
        right_idx = int(right_bases[peak_index_in_properties])
    else:
        left_idx = idx
        right_idx = idx
        while left_idx > 0 and corrected[left_idx] > corrected[left_idx - 1]:
            left_idx -= 1
        while right_idx < corrected.size - 1 and corrected[right_idx] > corrected[right_idx + 1]:
            right_idx += 1

    start_rt = float(rt_windowed[left_idx])
    end_rt = float(rt_windowed[right_idx])
    points = int(right_idx - left_idx + 1)

    area = float(np.trapz(corrected[left_idx : right_idx + 1], rt_windowed[left_idx : right_idx + 1]))
    sn = float(apex_intensity / noise) if noise > 0 else 0.0

    # FWHM interpolation.
    half = apex_intensity / 2.0
    fwhm = _interpolate_fwhm(rt_windowed, corrected, idx, half)

    # Asymmetry and tailing.
    before = rt_windowed[left_idx:idx]
    after = rt_windowed[idx : right_idx + 1]
    a = float((apex_rt - start_rt) / (end_rt - apex_rt)) if end_rt != apex_rt else 1.0
    tailing = float((end_rt - apex_rt) / (apex_rt - start_rt)) if start_rt != apex_rt else 1.0

    result.detection_status = 'detected'
    result.target_state = 'apex_candidate' if provisional else 'complete'
    result.observed_rt = apex_rt
    result.apex_intensity = float(intensity_windowed[idx])
    result.integrated_area = max(0.0, area)
    result.signal_to_noise = sn
    result.fwhm_minutes = fwhm
    result.points_across_peak = points
    result.asymmetry_factor = a
    result.tailing_factor = tailing
    result.integration_start_rt = start_rt
    result.integration_end_rt = end_rt

    _evaluate_quality(result, target, apex_rt, expected_rt, rt_window)
    return result


def _interpolate_fwhm(rt: np.ndarray, intensity: np.ndarray, apex_idx: int, half: float) -> Optional[float]:
    n = intensity.size
    if n < 2 or apex_idx < 0 or apex_idx >= n:
        return None
    left = apex_idx
    while left > 0 and intensity[left] > half:
        left -= 1
    right = apex_idx
    while right < n - 1 and intensity[right] > half:
        right += 1
    if left == 0 and intensity[left] > half:
        return None
    if right == n - 1 and intensity[right] > half:
        return None
    rt_left = _linear_interp(rt[left], rt[left + 1], intensity[left], intensity[left + 1], half)
    rt_right = _linear_interp(rt[right - 1], rt[right], intensity[right - 1], intensity[right], half)
    if rt_left is None or rt_right is None:
        return None
    return float(rt_right - rt_left)


def _linear_interp(x1: float, x2: float, y1: float, y2: float, y: float) -> Optional[float]:
    if y2 == y1:
        return None
    return x1 + (y - y1) * (x2 - x1) / (y2 - y1)


def _evaluate_quality(
    result: PeakResult,
    target: models.Target,
    observed_rt: float,
    expected_rt: Optional[float],
    rt_window: float,
) -> None:
    reasons = []
    if result.points_across_peak is not None and result.points_across_peak < target.minimum_points_across_peak:
        reasons.append('few_points_across_peak')
    if result.signal_to_noise is not None and result.signal_to_noise < target.minimum_signal_to_noise:
        reasons.append('low_signal_to_noise')
    if expected_rt is not None and abs(observed_rt - expected_rt) > 0.25:
        reasons.append('rt_shift')
    if expected_rt is not None and abs(observed_rt - expected_rt) > rt_window:
        result.target_state = 'outside_window'
        reasons.append('outside_rt_window')
    if result.mass_error_ppm is not None:
        low, high = _mz_window(target.target_mz, target.tolerance_value, target.tolerance_unit)
        if result.mass_error_ppm < (low - target.target_mz) / target.target_mz * 1e6 or result.mass_error_ppm > (high - target.target_mz) / target.target_mz * 1e6:
            reasons.append('mass_error')
    if result.fwhm_minutes is not None and target.maximum_fwhm_minutes and result.fwhm_minutes > target.maximum_fwhm_minutes:
        reasons.append('fwhm_above_threshold')
    if result.tailing_factor is not None:
        if result.tailing_factor > 2.0:
            reasons.append('peak_tailing')
        if result.tailing_factor < 0.5:
            reasons.append('peak_fronting')
    result.quality_reasons = reasons
    if not reasons:
        result.quality_class = 'good'
    elif 'low_signal_to_noise' in reasons or 'few_points_across_peak' in reasons:
        result.quality_class = 'poor'
    else:
        result.quality_class = 'warning'
