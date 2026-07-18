import { useEffect, useState } from 'react';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import type { Sample, SampleTarget, Sequence } from '../types';

interface ExportJob {
  id: string;
  export_type: string;
  status: string;
  file_key?: string;
}

export default function ExportData() {
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [targets, setTargets] = useState<SampleTarget[]>([]);
  const [selectedSequence, setSelectedSequence] = useState<string>('');
  const [selectedSample, setSelectedSample] = useState<string>('');
  const [selectedTarget, setSelectedTarget] = useState<string>('');
  const [exportType, setExportType] = useState<'tic' | 'xic'>('tic');
  const [jobs, setJobs] = useState<ExportJob[]>([]);
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

  useEffect(() => {
    if (!selectedSample) {
      setTargets([]);
      return;
    }
    api.get(`/samples/${selectedSample}/targets`).then((res) => {
      const targs: SampleTarget[] = res.data || [];
      setTargets(targs);
      if (exportType === 'xic' && targs.length && !selectedTarget) setSelectedTarget(targs[0].id);
    });
  }, [selectedSample, exportType]);

  const create = async () => {
    if (exportType === 'tic' && !selectedSample) return;
    if (exportType === 'xic' && !selectedTarget) return;
    const params = new URLSearchParams();
    params.set('export_type', exportType);
    if (exportType === 'tic') params.set('sample_id', selectedSample);
    if (exportType === 'xic') params.set('sample_target_id', selectedTarget);
    try {
      const res = await api.post(`/exports?${params.toString()}`);
      setJobs((prev) => [res.data, ...prev]);
      setMessage('Export queued.');
    } catch (err: any) {
      setMessage(err.response?.data?.error?.message || 'Export failed');
    }
  };

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold mb-2'>Export Data</h2>
        {message && <div className='mb-3 p-2 rounded text-[10px] bg-orbit-deep text-orbit-text'>{message}</div>}
        <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 items-end'>
          <select
            value={exportType}
            onChange={(e) => setExportType(e.target.value as 'tic' | 'xic')}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          >
            <option value='tic'>TIC (CSV)</option>
            <option value='xic'>XIC (CSV)</option>
          </select>
          <select
            value={selectedSequence}
            onChange={(e) => { setSelectedSequence(e.target.value); setSelectedSample(''); setSelectedTarget(''); }}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          >
            <option value=''>Sequence</option>
            {sequences.map((seq) => (<option key={seq.id} value={seq.id}>{seq.name}</option>))}
          </select>
          <select
            value={selectedSample}
            onChange={(e) => { setSelectedSample(e.target.value); setSelectedTarget(''); }}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          >
            <option value=''>Sample</option>
            {samples.map((s) => (<option key={s.id} value={s.id}>{s.sample_name}</option>))}
          </select>
          {exportType === 'xic' && (
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            >
              <option value=''>Target</option>
              {targets.map((t) => (<option key={t.id} value={t.id}>{t.target.compound_name}</option>))}
            </select>
          )}
          <button
            onClick={create}
            disabled={(exportType === 'tic' && !selectedSample) || (exportType === 'xic' && !selectedTarget)}
            className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px] disabled:opacity-50'
          >
            Export CSV
          </button>
        </div>
      </div>

      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit overflow-auto'>
        <table className='w-full border-collapse min-w-[500px] text-[10px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Export ID</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Type</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Status</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>File Key</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className='border-b border-orbit-border/5 hover:bg-orbit-hover'>
                <td className='p-2'>{job.id}</td>
                <td className='p-2'>{job.export_type}</td>
                <td className='p-2'><StatusBadge status={job.status} /></td>
                <td className='p-2 text-orbit-muted'>{job.file_key || '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
