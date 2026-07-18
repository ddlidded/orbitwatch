from __future__ import annotations

import math
from typing import Optional

import numpy as np


def _mz_window(target_mz: float, tolerance_value: float, tolerance_unit: str) -> tuple[float, float]:
    target_mz = float(target_mz)
    tolerance_value = float(tolerance_value)
    if tolerance_unit.lower() == 'ppm':
        delta = target_mz * tolerance_value * 1e-6
    elif tolerance_unit.lower() in ('da', 'th'):
        delta = abs(tolerance_value)
    else:
        delta = target_mz * 5.0 * 1e-6
    return target_mz - delta, target_mz + delta


def extract_xic_intensity(
    mz_array: list[float],
    intensity_array: list[float],
    target_mz: float,
    tolerance_value: float,
    tolerance_unit: str,
    scan_polarity: str,
    target_polarity: str,
) -> Optional[dict]:
    target_mz = float(target_mz)
    if scan_polarity.lower() != target_polarity.lower():
        return None
    if not mz_array or not intensity_array or len(mz_array) != len(intensity_array):
        return None
    low, high = _mz_window(target_mz, tolerance_value, tolerance_unit)
    mz = np.asarray(mz_array, dtype=np.float64)
    intens = np.asarray(intensity_array, dtype=np.float64)
    mask = (mz >= low) & (mz <= high)
    selected = intens[mask]
    if selected.size == 0:
        return None
    total = float(selected.sum())
    if total <= 0:
        return None
    selected_mz = mz[mask]
    centroid = float(np.sum(selected_mz * selected) / total)
    mass_error = (centroid - target_mz) / target_mz * 1e6
    return {
        'intensity': total,
        'observed_centroid_mz': centroid,
        'mass_error_ppm': mass_error,
    }


def calculate_tic(intensity_array: list[float]) -> float:
    if not intensity_array:
        return 0.0
    return float(np.sum(np.asarray(intensity_array, dtype=np.float64)))
