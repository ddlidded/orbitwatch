import { useEffect, useState } from 'react';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import type { Sample, Sequence } from '../types';

interface ReportJob {
  id: string;
  sample_id: string;
  status: string;
  file_key?: string;
  created_at: string;
}

export default function Reports() {
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [selectedSequence, setSelectedSequence] = useState<string>('');
  const [selectedSample, setSelectedSample] = useState<string>('');
  const [jobs, setJobs] = useState<ReportJob[]>([]);
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get('/sequences?limit=100').then((res) => {
      const seqs: Sequence[] = res.data.items || [];
      setSequences(seqs);
      if (seqs.length && !selectedSequence) setSelectedSequence(seqs[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selectedSequence) {
      setSamples([]);
      return;
    }
    api.get(`/sequences/${selectedSequence}/samples?limit=200`).then((res) => {
      const samps: Sample[] = res.data.items || [];
      setSamples(samps);
      if (samps.length && !selectedSample) setSelectedSample(samps[0].id);
    });
  }, [selectedSequence]);

  const create = async () => {
    if (!selectedSample) return;
    try {
      const res = await api.post(`/reports?report_type=sample&sample_id=${selectedSample}`);
      setJobs((prev) => [res.data, ...prev]);
      setMessage('Report generation started.');
    } catch (err: any) {
      setMessage(err.response?.data?.error?.message || 'Failed to create report');
    }
  };

  const refresh = (job: ReportJob) => {
    api.get(`/reports/${job.id}`).then((res) => {
      setJobs((prev) => prev.map((j) => (j.id === job.id ? res.data : j)));
    }).catch(() => {});
  };

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold mb-2'>Sample Reports</h2>
        {message && <div className='mb-3 p-2 rounded text-[10px] bg-orbit-deep text-orbit-text'>{message}</div>}
        <div className='flex flex-wrap items-end gap-3'>
          <select
            value={selectedSequence}
            onChange={(e) => { setSelectedSequence(e.target.value); setSelectedSample(''); }}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none min-w-[220px]'
          >
            <option value=''>Select sequence</option>
            {sequences.map((seq) => (<option key={seq.id} value={seq.id}>{seq.name}</option>))}
          </select>
          <select
            value={selectedSample}
            onChange={(e) => setSelectedSample(e.target.value)}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none min-w-[220px]'
          >
            <option value=''>Select sample</option>
            {samples.map((s) => (<option key={s.id} value={s.id}>{s.sample_name}</option>))}
          </select>
          <button
            onClick={create}
            disabled={!selectedSample}
            className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px] disabled:opacity-50'
          >
            Generate PDF
          </button>
        </div>
      </div>

      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit overflow-auto'>
        <table className='w-full border-collapse min-w-[500px] text-[10px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Report ID</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Sample</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Status</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>File Key</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className='border-b border-orbit-border/5 hover:bg-orbit-hover'>
                <td className='p-2'>{job.id}</td>
                <td className='p-2'>{job.sample_id}</td>
                <td className='p-2'><StatusBadge status={job.status} /></td>
                <td className='p-2 text-orbit-muted'>{job.file_key || '–'}</td>
                <td className='p-2'>
                  <button onClick={() => refresh(job)} className='h-[24px] px-2 rounded bg-orbit-soft border border-orbit-border text-orbit-text text-[9px] mr-1'>Refresh</button>
                  {job.status === 'completed' && (
                    <a
                      href={`/api/v1/reports/${job.id}/download`}
                      className='inline-block h-[24px] px-2 rounded bg-orbit-blue text-white text-[9px] leading-[24px]'
                      download
                    >
                      Download
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
