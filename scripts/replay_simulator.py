#!/usr/bin/env python3
"""OrbitWatch replay simulator.

Sends deterministic synthetic LC-MS data to the backend agent endpoints so the
frontend can be verified with live-like data without a real instrument.
"""
import base64
import csv
import io
import math
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
API = f'{BASE}/api/v1'
ADMIN_EMAIL = 'admin@isotopiq.dev'
ADMIN_PASSWORD = 'OrbitWatch-Admin-2024!'


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def login():
    r = requests.post(f'{API}/auth/login', json={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD})
    r.raise_for_status()
    return r.cookies


def register_agent():
    payload = {
        'hostname': 'simulator-agent',
        'agent_version': '0.0.1-sim',
        'instrument_serial': 'IQLAAEGAAPFADBMK',
        'instrument_name': 'Exploris 480 (Replay)',
        'model': 'Orbitrap Exploris 480',
        'api_version': '3.8.0.57',
        'tune_version': '3.4.0.3122',
        'iapi_version': '3.8.0.57',
        'capabilities': {'scan': True, 'telemetry': True, 'rawfile': True},
    }
    r = requests.post(f'{API}/agents/register', json=payload)
    r.raise_for_status()
    return r.json()


def create_target_list(cookies: dict, instrument_id: str) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            'Compound',
            'Formula',
            'Adduct',
            'TargetMz',
            'MassTolerance',
            'ToleranceUnit',
            'Polarity',
            'ExpectedRT',
            'RTWindow',
            'MinimumSN',
            'MinimumPointsAcrossPeak',
            'Enabled',
        ],
    )
    writer.writeheader()
    targets = [
        {'Compound': 'SAM', 'Formula': 'C15H22N6O5S', 'Adduct': '[M+H]+', 'TargetMz': '', 'ExpectedRT': '6.42', 'Polarity': 'positive'},
        {'Compound': 'SAH', 'Formula': 'C14H20N6O5S', 'Adduct': '[M+H]+', 'TargetMz': '', 'ExpectedRT': '5.88', 'Polarity': 'positive'},
        {'Compound': 'Betaine', 'Formula': 'C5H11NO2', 'Adduct': '[M+H]+', 'TargetMz': '', 'ExpectedRT': '4.80', 'Polarity': 'positive'},
        {'Compound': 'Citrate', 'Formula': 'C6H8O7', 'Adduct': '[M-H]-', 'TargetMz': '', 'ExpectedRT': '7.19', 'Polarity': 'negative'},
        {'Compound': 'Adenosine', 'Formula': 'C10H13N5O4', 'Adduct': '[M+H]+', 'TargetMz': '', 'ExpectedRT': '4.55', 'Polarity': 'positive'},
    ]
    for t in targets:
        writer.writerow({
            'Compound': t['Compound'],
            'Formula': t['Formula'],
            'Adduct': t['Adduct'],
            'TargetMz': t['TargetMz'],
            'MassTolerance': '5',
            'ToleranceUnit': 'ppm',
            'Polarity': t['Polarity'],
            'ExpectedRT': t['ExpectedRT'],
            'RTWindow': '0.5',
            'MinimumSN': '3',
            'MinimumPointsAcrossPeak': '7',
            'Enabled': 'true',
        })
    files = {'file': ('targets.csv', buf.getvalue().encode(), 'text/csv')}
    data = {'name': 'Default Replay Targets', 'description': 'Synthetic target list for replay mode'}
    r = requests.post(f'{API}/target-lists/import', data=data, files=files, cookies=cookies)
    r.raise_for_status()
    tl_id = r.json()['id']
    requests.post(f'{API}/target-lists/{tl_id}/assign', params={'instrument_id': instrument_id}, cookies=cookies)
    return tl_id


def send_message(token: str, msg_type: str, payload: dict, agent_id: str, instrument_id: str, seq: int):
    env = {
        'schemaVersion': '1.0',
        'messageId': str(uuid.uuid4()),
        'agentId': agent_id,
        'instrumentId': instrument_id,
        'sequenceNumber': seq,
        'sentAt': now_iso(),
        'type': msg_type,
        'payload': payload,
    }
    r = requests.post(f'{API}/agents/messages', json=env, headers={'x-agent-token': token})
    r.raise_for_status()
    return r.json()


def generate_mz_intensity_arrays(rt: float, peaks: list, noise: float = 5.0):
    """Produce m/z and intensity arrays with peaks at known target m/zs."""
    mzs = []
    intensities = []
    # background noise across 50-500 m/z at 0.1 Da steps
    for mz in [50 + i * 0.1 for i in range(4501)]:
        base = random.uniform(0, noise) + noise * 0.5
        for p in peaks:
            if p.get('mz'):
                sigma = 0.005
                base += p['intensity'] * math.exp(-((mz - p['mz']) ** 2) / (2 * sigma**2))
        if base > noise * 0.2:
            mzs.append(round(mz, 3))
            intensities.append(round(base, 1))
    return mzs, intensities


def main():
    print('Logging in as admin...')
    cookies = login()

    print('Registering agent...')
    reg = register_agent()
    token = reg['token']
    agent_id = reg['agent_id']
    instrument_id = reg['instrument_id']
    print(f'Agent {agent_id} instrument {instrument_id}')

    print('Uploading target list...')
    create_target_list(cookies, instrument_id)

    external_sequence_id = 'SEQ-2026-07-18-001'
    external_sample_id = 'SMP-001'

    print('Starting sequence...')
    send_message(
        token,
        'sequence.started',
        {
            'external_sequence_id': external_sequence_id,
            'sequence_name': 'Replay QC Sequence',
            'started_at': now_iso(),
            'samples': [
                {
                    'external_sample_id': external_sample_id,
                    'position': 1,
                    'sample_name': 'QC-Replay-01',
                    'sample_type': 'QC',
                    'method_name': 'HILIC-pos-neg',
                    'polarity': 'positive',
                    'vial_position': 'A1',
                    'raw_file_name': 'QC_Replay_01.raw',
                    'expected_runtime_seconds': 900,
                    'status': 'queued',
                }
            ],
        },
        agent_id,
        instrument_id,
        1,
    )

    print('Starting sample...')
    send_message(
        token,
        'sample.started',
        {
            'external_sequence_id': external_sequence_id,
            'external_sample_id': external_sample_id,
            'started_at': now_iso(),
        },
        agent_id,
        instrument_id,
        2,
    )

    print('Streaming scans (Ctrl-C to stop)...')
    # Deterministic peaks per compound
    compounds = {
        'SAM': {'mz': 399.1448, 'rt': 6.42, 'intensity': 2.8e6, 'sigma_rt': 0.12},
        'SAH': {'mz': 385.1292, 'rt': 5.88, 'intensity': 1.3e6, 'sigma_rt': 0.10},
        'Betaine': {'mz': 118.0864, 'rt': 4.80, 'intensity': 8.0e3, 'sigma_rt': 0.08},
        'Citrate': {'mz': 191.0191, 'rt': 7.19, 'intensity': 4.0e5, 'sigma_rt': 0.14},
        'Adenosine': {'mz': 268.1030, 'rt': 4.55, 'intensity': 1.0e5, 'sigma_rt': 0.10},
    }
    seq = 3
    scan_number = 1
    rng = random.Random(42)
    try:
        while scan_number <= 300:
            rt = scan_number * 0.05  # minutes
            progress = min(100, int(rt / 15 * 100))
            tic = 1.5e6
            peaks = []
            for comp, info in compounds.items():
                elution = info['intensity'] * math.exp(-((rt - info['rt']) ** 2) / (2 * info['sigma_rt'] ** 2))
                if elution > 1000:
                    peaks.append({'mz': info['mz'], 'intensity': elution})
                tic += elution
            # Add small baseline
            tic += rng.uniform(0, 5e4)
            mz_array, intensity_array = generate_mz_intensity_arrays(rt, peaks, noise=500)
            payload = {
                'external_sequence_id': external_sequence_id,
                'external_sample_id': external_sample_id,
                'scan_number': scan_number,
                'retention_time_minutes': round(rt, 3),
                'ms_order': 1,
                'polarity': 'positive',
                'scan_type': 'Full',
                'tic': round(tic, 1),
                'base_peak_mz': peaks[0]['mz'] if peaks else 0,
                'base_peak_intensity': round(peaks[0]['intensity'], 1) if peaks else 0,
                'low_mz': min(mz_array) if mz_array else 50,
                'high_mz': max(mz_array) if mz_array else 500,
                'mz_array': mz_array,
                'intensity_array': intensity_array,
            }
            send_message(token, 'scan', payload, agent_id, instrument_id, seq)
            seq += 1
            scan_number += 1
            time.sleep(0.5)

        print('Completing sample...')
        send_message(
            token,
            'sample.completed',
            {
                'external_sequence_id': external_sequence_id,
                'external_sample_id': external_sample_id,
                'completed_at': now_iso(),
            },
            agent_id,
            instrument_id,
            seq,
        )
        print('Replay complete.')
    except KeyboardInterrupt:
        print('Interrupted.')


if __name__ == '__main__':
    main()
