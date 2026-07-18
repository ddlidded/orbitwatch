import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../api/client';
import TicChart from '../components/TicChart';
import type { Sample, Sequence, TicPoint } from '../types';

export default function TicOverview() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [selectedSequenceId, setSelectedSequenceId] = useState<string>(searchParams.get('sequence') || '');
  const [selectedSampleId, setSelectedSampleId] = useState<string>(searchParams.get('sample') || '');
  const [tic, setTic] = useState<TicPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/sequences?limit=100').then((res) => {
      const seqs: Sequence[] = res.data.items || [];
      setSequences(seqs);
      if (!selectedSequenceId && seqs.length) {
        setSelectedSequenceId(seqs[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedSequenceId) {
      setSamples([]);
      return;
    }
    api.get(`/sequences/${selectedSequenceId}/samples?limit=200`).then((res) => {
      const samps: Sample[] = res.data.items || [];
      setSamples(samps);
      if (samps.length && !selectedSampleId) {
        setSelectedSampleId(samps[0].id);
      }
    });
  }, [selectedSequenceId]);

  useEffect(() => {
    if (!selectedSampleId) {
      setTic([]);
      return;
    }
    setLoading(true);
    api.get(`/samples/${selectedSampleId}/tic?limit=50000`)
      .then((res) => setTic(res.data.items || []))
      .finally(() => setLoading(false));
    setSearchParams({ sequence: selectedSequenceId, sample: selectedSampleId });
  }, [selectedSampleId, selectedSequenceId, setSearchParams]);

  const sample = samples.find((s) => s.id === selectedSampleId);

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <div className='flex flex-wrap items-end gap-3'>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Sequence</label>
            <select
              value={selectedSequenceId}
              onChange={(e) => {
                setSelectedSequenceId(e.target.value);
                setSelectedSampleId('');
              }}
              className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none min-w-[220px]'
            >
              <option value=''>Select sequence</option>
              {sequences.map((seq) => (
                <option key={seq.id} value={seq.id}>{seq.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Sample</label>
            <select
              value={selectedSampleId}
              onChange={(e) => setSelectedSampleId(e.target.value)}
              className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none min-w-[220px]'
            >
              <option value=''>Select sample</option>
              {samples.map((s) => (
                <option key={s.id} value={s.id}>{s.sample_name}</option>
              ))}
            </select>
          </div>
          {sample && (
            <div className='text-[11px] text-orbit-muted'>
              {sample.sample_type} | {sample.polarity} | {sample.acquisition_status} | {sample.progress_pct}%
            </div>
          )}
        </div>
      </div>

      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit min-h-[400px]'>
        <div className='flex items-start justify-between mb-2'>
          <h2 className='text-[13px] font-semibold'>
            Total Ion Current {sample ? `— ${sample.sample_name}` : ''}
          </h2>
          <span className='text-[10px] text-orbit-muted'>{tic.length.toLocaleString()} points</span>
        </div>
        {loading && <div className='text-orbit-muted text-xs'>Loading TIC…</div>}
        <TicChart data={tic} sampleName={sample?.sample_name} height={360} />
      </div>
    </div>
  );
}
