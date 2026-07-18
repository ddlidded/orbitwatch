import { useState } from 'react';
import type { PeakRow } from '../types';
import StatusBadge from './StatusBadge';

function XicPreview({ color, missing }: { color: string; missing?: boolean }) {
  if (missing) {
    return (
      <svg className='w-[165px] h-[38px]' viewBox='0 0 165 38'>
        <line x1='0' y1='30' x2='165' y2='30' stroke={color} strokeDasharray='5 4' opacity='0.65' />
      </svg>
    );
  }
  const c = 82;
  const wd = 11;
  const points: string[] = [];
  for (let x = 0; x <= 165; x += 4) {
    const y = 30 - 23 * Math.exp(-Math.pow(x - c, 2) / (2 * wd * wd)) + Math.sin(x / 7) * 1.2 + (Math.random() - 0.5) * 1.5;
    points.push(`${x},${Math.max(4, Math.min(31, y)).toFixed(1)}`);
  }
  return (
    <svg className='w-[165px] h-[38px]' viewBox='0 0 165 38'>
      <line x1={c - 20} y1='2' x2={c - 20} y2='34' stroke='#6b7788' strokeDasharray='4 4' opacity='0.65' />
      <line x1={c + 20} y1='2' x2={c + 20} y2='34' stroke='#6b7788' strokeDasharray='4 4' opacity='0.65' />
      <polyline points={points.join(' ')} fill='none' stroke={color} strokeWidth='1.6' />
      <line x1={c} y1='3' x2={c} y2='34' stroke={color} opacity='0.85' />
    </svg>
  );
}

export default function PeakMonitor({ peaks }: { peaks: PeakRow[] }) {
  const [filter, setFilter] = useState('all');
  const filtered = peaks.filter((p) => filter === 'all' || p.filter === filter);

  return (
    <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit h-full'>
      <div className='flex items-start justify-between mb-2'>
        <h2 className='text-[13px] font-semibold'>Peak Monitor</h2>
        <button className='h-[30px] px-3 rounded-md bg-orbit-soft border border-orbit-border text-orbit-text text-[10px]'>Export CSV</button>
      </div>
      <select
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className='h-[30px] px-2 rounded-md bg-orbit-soft border border-orbit-border text-orbit-text text-[10px] mb-2.5'
      >
        <option value='all'>All Targets ({peaks.length})</option>
        <option value='good'>Good</option>
        <option value='warning'>Warnings</option>
        <option value='missing'>Not Detected</option>
      </select>
      <div className='overflow-auto'>
        <table className='w-full border-collapse min-w-[900px] text-[9px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Compound</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>m/z</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Status</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Live XIC</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>RT (min)</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Apex Int.</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>S/N</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Peak Shape</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <tr key={p.compound_name} className='border-b border-orbit-border/5 hover:bg-orbit-hover'>
                <td className='p-2'>
                  <b className='block text-[10px]'>{p.compound_name}</b>
                  <span className='text-orbit-muted'>{p.adduct || ''}</span>
                </td>
                <td className='p-2'>{p.target_mz}</td>
                <td className='p-2'><StatusBadge status={p.statusClass} /></td>
                <td className='p-2'><XicPreview color={p.color || '#3ecf66'} missing={p.filter === 'missing'} /></td>
                <td className='p-2'>
                  <b>{p.rt?.toFixed(2) || '–'}</b>
                  <div className='text-orbit-muted mt-0.5'>Exp. {p.expected_rt?.toFixed(2) || '–'}</div>
                </td>
                <td className='p-2'>{p.apex_intensity != null ? p.apex_intensity.toExponential(2) : '–'}</td>
                <td className='p-2'>{p.sn?.toFixed(1) || '–'}</td>
                <td className={`p-2 ${p.shapeClass || ''}`}>{p.shape || '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
