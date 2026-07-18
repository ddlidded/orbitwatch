from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import pandas as pd
from molmass import Formula
from sqlalchemy.orm import Session

from app import models

VALID_ADDUCTS = {'[M+H]+', '[M-H]-', '[M+Na]+', '[M+K]+', '[M+NH4]+', '[M+HCOO]-', '[M+CH3COO]-'}
TOLERANCE_UNITS = {'ppm', 'da'}


def parse_adduct_mz_delta(adduct: str) -> float:
    # Very small subset for illustration. Returns signed mass delta (protonation etc.).
    mapping = {
        '[M+H]+': 1.007276,
        '[M+Na]+': 22.989218,
        '[M+K]+': 38.963158,
        '[M+NH4]+': 18.033823,
        '[M-H]-': -1.007276,
        '[M+HCOO]-': 44.998201,
        '[M+CH3COO]-': 59.013851,
    }
    return mapping.get(adduct, 0.0)


def formula_to_mz(formula: str, adduct: Optional[str] = None) -> Optional[float]:
    try:
        f = Formula(formula)
        neutral = f.isotope.mass
    except Exception:
        return None
    delta = parse_adduct_mz_delta(adduct) if adduct else 0.0
    return neutral + delta


def _normalize_polarity(value: Any) -> str:
    if value is None:
        return 'positive'
    v = str(value).strip().lower()
    if v in ('pos', '+', 'positive', '1'):
        return 'positive'
    if v in ('neg', '-', 'negative', '0'):
        return 'negative'
    return v


def _clean_numeric(value: Any, default: Any = None):
    if value is None or str(value).strip() == '':
        return default
    try:
        return float(str(value).replace(',', ''))
    except Exception:
        return None


def _get(row: pd.Series, *keys: str) -> Any:
    for key in keys:
        if key in row.index:
            return row[key]
    return None


def _validate_row(row: pd.Series) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    compound = str(_get(row, 'compound', 'compound_name', 'Compound', 'CompoundName') or '').strip()
    if not compound:
        errors.append('Compound is required')

    polarity = _normalize_polarity(_get(row, 'polarity', 'Polarity'))
    if not polarity:
        errors.append('Polarity is required')

    formula = str(_get(row, 'formula', 'Formula') or '').strip() or None
    adduct = str(_get(row, 'adduct', 'Adduct') or '').strip() or None
    target_mz_raw = _clean_numeric(_get(row, 'target_mz', 'targetmz', 'm/z', 'mz', 'target_mz', 'TargetMz'))
    calculated_mz: Optional[float] = None

    if target_mz_raw is None:
        if formula:
            if adduct and adduct not in VALID_ADDUCTS:
                warnings.append(f'Unrecognized adduct: {adduct}')
            calculated_mz = formula_to_mz(formula, adduct)
            if calculated_mz is None:
                errors.append('Could not calculate m/z from formula/adduct')
            else:
                warnings.append('TargetMz was calculated from formula/adduct')
        else:
            errors.append('TargetMz or Formula+Adduct is required')
    else:
        if formula and adduct:
            calculated_mz = formula_to_mz(formula, adduct)
            if calculated_mz and abs(calculated_mz - target_mz_raw) > 0.01:
                warnings.append('Calculated m/z differs from supplied TargetMz')

    tolerance_value = _clean_numeric(_get(row, 'tolerance_value', 'mass_tolerance', 'masstolerance', 'MassTolerance'), 5.0)
    tolerance_unit = str(_get(row, 'tolerance_unit', 'ToleranceUnit', 'toleranceunit') or 'ppm').strip().lower()
    if tolerance_unit not in TOLERANCE_UNITS:
        warnings.append(f'Unrecognized tolerance unit {tolerance_unit}; defaulting to ppm')
        tolerance_unit = 'ppm'

    expected_rt = _clean_numeric(_get(row, 'expected_rt', 'expected_rt_minutes', 'expectedrt', 'ExpectedRT'))
    rt_window = _clean_numeric(_get(row, 'rt_window', 'rt_window_minutes', 'rtwindow', 'RTWindow'), 0.5)
    min_sn = _clean_numeric(_get(row, 'minimum_sn', 'minimum_signal_to_noise', 'MinimumSN'), 3.0)
    min_points = int(_clean_numeric(_get(row, 'minimum_points', 'minimum_points_across_peak', 'MinimumPointsAcrossPeak'), 7) or 7)
    max_fwhm = _clean_numeric(_get(row, 'maximum_fwhm', 'maximum_fwhm_minutes', 'MaximumFWHM'))
    enabled = str(_get(row, 'enabled', 'Enabled') or 'true').lower() in ('true', '1', 'yes', 'y')

    return {
        'compound_name': compound,
        'formula': formula,
        'adduct': adduct,
        'target_mz': target_mz_raw if target_mz_raw is not None else calculated_mz,
        'mz_source': 'user' if target_mz_raw is not None else 'calculated',
        'calculated_mz': calculated_mz,
        'polarity': polarity,
        'expected_rt_minutes': expected_rt,
        'rt_window_minutes': rt_window,
        'tolerance_value': tolerance_value,
        'tolerance_unit': tolerance_unit,
        'minimum_signal_to_noise': min_sn,
        'minimum_points_across_peak': min_points,
        'maximum_fwhm_minutes': max_fwhm,
        'enabled': enabled,
        'warnings': warnings,
        'errors': errors,
    }


def parse_target_list(
    content: bytes, filename: str
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    stream = io.BytesIO(content)
    if filename.lower().endswith('.csv'):
        df = pd.read_csv(stream, dtype=str, keep_default_na=False)
    elif filename.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(stream, dtype=str, keep_default_na=False)
    else:
        raise ValueError('Only CSV and XLSX target lists are supported')

    df.columns = [c.strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    seen = set()
    previews = []
    for idx, row in df.iterrows():
        parsed = _validate_row(row)
        parsed['original_row'] = int(idx) + 2
        key = (parsed['compound_name'].lower(), parsed['polarity'], parsed.get('target_mz'))
        if key in seen:
            parsed['duplicate_status'] = 'duplicate'
            parsed['errors'].append('Duplicate definition')
        else:
            seen.add(key)
        previews.append(parsed)
    return df, previews


def create_target_list_version(
    db: Session,
    owner_id: str,
    name: str,
    description: Optional[str],
    content: bytes,
    filename: str,
) -> models.TargetList:
    checksum = hashlib.sha256(content).hexdigest()
    target_list = models.TargetList(
        name=name,
        description=description,
        owner_id=UUID(owner_id),
    )
    db.add(target_list)
    db.flush()

    version_number = (
        db.query(models.TargetListVersion)
        .filter_by(target_list_id=target_list.id)
        .count()
        + 1
    )
    version = models.TargetListVersion(
        target_list_id=target_list.id,
        version_number=version_number,
        uploaded_file_path=filename,
        uploaded_file_checksum=checksum,
        uploaded_by_user_id=UUID(owner_id),
    )
    db.add(version)
    db.flush()

    df, previews = parse_target_list(content, filename)
    for preview in previews:
        if preview['errors']:
            continue
        db.add(
            models.Target(
                target_list_version_id=version.id,
                compound_name=preview['compound_name'],
                formula=preview['formula'],
                adduct=preview['adduct'],
                target_mz=preview['target_mz'],
                mz_source=preview['mz_source'],
                polarity=preview['polarity'],
                expected_rt_minutes=preview['expected_rt_minutes'],
                rt_window_minutes=preview['rt_window_minutes'],
                tolerance_value=preview['tolerance_value'],
                tolerance_unit=preview['tolerance_unit'],
                minimum_signal_to_noise=preview['minimum_signal_to_noise'],
                minimum_points_across_peak=preview['minimum_points_across_peak'],
                maximum_fwhm_minutes=preview['maximum_fwhm_minutes'],
                enabled=preview['enabled'],
            )
        )

    target_list.active_version_id = version.id
    db.commit()
    return target_list
