import { Search } from 'lucide-react';
import { useState } from 'react';
import type { Sample } from '../types';
import StatusBadge from './StatusBadge';

interface SequenceQueueProps {
  samples: Sample[];
}

export default function SequenceQueue({ samples }: SequenceQueueProps) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  const filtered = samples.filter((s) => {
    if (filter !== 'all' && s.acquisition_status !== filter) return false;
    if (search && !s.sample_name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const counts = {
    all: samples.length,
    running: samples.filter((s) => s.acquisition_status === 'running').length,
    queued: samples.filter((s) => s.acquisition_status === 'queued').length,
    completed: samples.filter((s) => s.acquisition_status === 'completed').length,
    failed: samples.filter((s) => s.acquisition_status === 'failed').length,
  };

  return (
    <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit h-full'>
      <h2 className='text-[13px] font-semibold mb-2'>Sequence Queue</h2>
      <div className='flex items-center justify-between gap-2 mb-2.5'>
        <div className='relative flex-1 max-w-[260px]'>
          <Search size={13} className='absolute left-2 top-2 text-orbit-muted' />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder='Search samples...'
            className='w-full h-[30px] rounded-md border border-orbit-border bg-orbit-soft text-orbit-text pl-7 pr-2 text-[10px] outline-none'
          />
        </div>
        <button className='h-[30px] px-3 rounded-md bg-orbit-soft border border-orbit-border text-orbit-text text-[10px]'>
          Export CSV
        </button>
      </div>
      <div className='flex flex-wrap gap-1.5 mb-2.5'>
        {['all', 'running', 'queued', 'completed', 'failed'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-2.5 py-1 rounded-full text-[9px] ${
              filter === f ? 'bg-[rgba(43,134,229,0.16)] text-[#5ca3ff]' : 'bg-orbit-deep text-orbit-muted'
            }`}
          >
            {f[0].toUpperCase() + f.slice(1)} <span className='ml-1 px-1 rounded-full bg-white/5'>{counts[f as keyof typeof counts]}</span>
          </button>
        ))}
      </div>
      <div className='overflow-auto'>
        <table className='w-full border-collapse min-w-[620px] text-[9px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Position</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Sample Name</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Type</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Status</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>RT (min)</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>TIC (Live)</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Progress</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr
                key={s.id}
                className={`border-b border-orbit-border/5 hover:bg-orbit-hover ${s.acquisition_status === 'running' ? 'bg-[rgba(43,134,229,0.16)]' : ''}`}
              >
                <td className='p-2'>{s.acquisition_status === 'running' ? `▶ ${s.position}` : s.position}</td>
                <td className='p-2'>{s.sample_name}</td>
                <td className='p-2 text-orbit-muted'>{s.sample_type || 'Unknown'}</td>
                <td className='p-2'><StatusBadge status={s.acquisition_status} /></td>
                <td className='p-2'>{s.started_at ? '—' : '–'}</td>
                <td className='p-2'>{s.progress_pct ? `${s.progress_pct}%` : '–'}</td>
                <td className='p-2'>
                  <span className='inline-block w-[42px] h-[5px] bg-orbit-deep rounded-full overflow-hidden mr-1 align-middle'>
                    <span
                      className='block h-full rounded-full'
                      style={{
                        width: `${s.progress_pct || 0}%`,
                        background: s.progress_pct === 100 ? 'var(--green)' : 'linear-gradient(90deg,#2a70ed,#5b9cff)',
                      }}
                    />
                  </span>
                  {s.progress_pct || 0}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
