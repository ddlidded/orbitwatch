import { useEffect, useState } from 'react';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import type { Sample, Sequence } from '../types';

export default function SequenceQueuePage() {
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [samplesBySequence, setSamplesBySequence] = useState<Record<string, Sample[]>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.get('/sequences?limit=100').then((res) => {
      const seqs: Sequence[] = res.data.items || [];
      setSequences(seqs);
      if (seqs.length) setExpanded(new Set([seqs[0].id]));
    });
  }, []);

  useEffect(() => {
    Array.from(expanded).forEach((seqId) => {
      if (samplesBySequence[seqId]) return;
      api.get(`/sequences/${seqId}/samples?limit=200`).then((res) => {
        setSamplesBySequence((prev) => ({ ...prev, [seqId]: res.data.items || [] }));
      });
    });
  }, [expanded, samplesBySequence]);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold'>Sequence Queue</h2>
      </div>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit overflow-auto'>
        <table className='w-full border-collapse min-w-[800px] text-[10px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'></th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Sequence</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Status</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Samples</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Started</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Completed</th>
            </tr>
          </thead>
          <tbody>
            {sequences.map((seq) => (
              <>
                <tr key={seq.id} className='border-b border-orbit-border/10 hover:bg-orbit-hover cursor-pointer' onClick={() => toggle(seq.id)}>
                  <td className='p-2'>{expanded.has(seq.id) ? '▼' : '▶'}</td>
                  <td className='p-2 font-semibold'>{seq.name}</td>
                  <td className='p-2'><StatusBadge status={seq.status} /></td>
                  <td className='p-2'>{seq.sample_count}</td>
                  <td className='p-2'>{seq.started_at ? new Date(seq.started_at).toLocaleString() : '–'}</td>
                  <td className='p-2'>{seq.completed_at ? new Date(seq.completed_at).toLocaleString() : '–'}</td>
                </tr>
                {expanded.has(seq.id) && (
                  <tr>
                    <td colSpan={6} className='p-0'>
                      <div className='bg-orbit-soft/50 p-2'>
                        <table className='w-full border-collapse text-[10px]'>
                          <thead>
                            <tr className='text-left text-orbit-muted'>
                              <th className='p-2 font-semibold'>Position</th>
                              <th className='p-2 font-semibold'>Sample</th>
                              <th className='p-2 font-semibold'>Type</th>
                              <th className='p-2 font-semibold'>Method</th>
                              <th className='p-2 font-semibold'>Status</th>
                              <th className='p-2 font-semibold'>Progress</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(samplesBySequence[seq.id] || []).map((s) => (
                              <tr key={s.id} className='border-b border-orbit-border/5'>
                                <td className='p-2'>{s.position}</td>
                                <td className='p-2'>{s.sample_name}</td>
                                <td className='p-2'>{s.sample_type}</td>
                                <td className='p-2'>{s.method_name}</td>
                                <td className='p-2'><StatusBadge status={s.acquisition_status} /></td>
                                <td className='p-2'>
                                  <span className='inline-block w-[60px] h-[5px] bg-orbit-deep rounded-full overflow-hidden mr-1 align-middle'>
                                    <span className='block h-full rounded-full bg-orbit-blue' style={{ width: `${s.progress_pct || 0}%` }} />
                                  </span>
                                  {s.progress_pct || 0}%
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
