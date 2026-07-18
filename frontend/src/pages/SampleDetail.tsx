import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api/client';
import TicChart from '../components/TicChart';
import StatusBadge from '../components/StatusBadge';
import type { PeakMetric, Sample, SampleTarget, XicPoint } from '../types';

interface TargetRow extends SampleTarget {
  peak?: PeakMetric;
  xic?: XicPoint[];
}

export default function SampleDetail() {
  const { sampleId } = useParams<{ sampleId: string }>();
  const navigate = useNavigate();
  const [sample, setSample] = useState<Sample | null>(null);
  const [rows, setRows] = useState<TargetRow[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [loading, setLoading] = useState(true);

  const effectiveId = sampleId === 'current' ? '' : sampleId || '';

  useEffect(() => {
    if (!effectiveId) {
      api.get('/dashboard/summary').then((res) => {
        const id = res.data.current_sample?.id;
        if (id) navigate(`/samples/${id}`, { replace: true });
      });
      return;
    }
    setLoading(true);
    api.get(`/samples/${effectiveId}`).then((res) => setSample(res.data));
    api.get(`/samples/${effectiveId}/targets`)
      .then((res) => setRows(res.data.map((t: SampleTarget) => ({ ...t, peak: undefined, xic: undefined }))))
      .finally(() => setLoading(false));
  }, [effectiveId]);

  useEffect(() => {
    if (!rows.length || !effectiveId) return;
    rows.forEach((row) => {
      api.get(`/samples/${effectiveId}/targets/${row.target_id}/peak?provisional=true`)
        .then((res) => {
          setRows((prev) => prev.map((r) => (r.target_id === row.target_id ? { ...r, peak: res.data } : r)));
        })
        .catch(() => {});
    });
  }, [rows.length, effectiveId]);

  const selectTarget = (row: TargetRow) => {
    setSelected(row.target_id);
    if (row.xic) return;
    api.get(`/samples/${effectiveId}/targets/${row.target_id}/xic`)
      .then((res) => {
        setRows((prev) => prev.map((r) => (r.target_id === row.target_id ? { ...r, xic: res.data } : r)));
      })
      .catch(() => {});
  };

  const selectedRow = rows.find((r) => r.target_id === selected);

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold'>{sample?.sample_name || 'Sample Detail'}</h2>
        <div className='text-[11px] text-orbit-muted mt-1'>
          {sample ? (
            <>
              {sample.sample_type} | {sample.method_name} | {sample.polarity} | Status: <StatusBadge status={sample.acquisition_status} />
            </>
          ) : (
            'Loading…'
          )}
        </div>
      </div>

      {loading && <div className='text-orbit-muted text-xs'>Loading targets…</div>}

      <div className='grid grid-cols-1 xl:grid-cols-[1fr_0.55fr] gap-2.5'>
        <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit overflow-auto'>
          <table className='w-full border-collapse min-w-[700px] text-[10px]'>
            <thead>
              <tr className='text-left text-orbit-muted'>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Compound</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>m/z</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Polarity</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Exp. RT</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>State</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Obs. RT</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Apex</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>S/N</th>
                <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Quality</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.target_id}
                  onClick={() => selectTarget(row)}
                  className={`border-b border-orbit-border/5 hover:bg-orbit-hover cursor-pointer ${selected === row.target_id ? 'bg-orbit-hover' : ''}`}
                >
                  <td className='p-2'>
                    <b>{row.target.compound_name}</b>
                    <div className='text-orbit-muted'>{row.target.adduct}</div>
                  </td>
                  <td className='p-2'>{row.target.target_mz}</td>
                  <td className='p-2'>{row.target.polarity}</td>
                  <td className='p-2'>{row.target.expected_rt_minutes}</td>
                  <td className='p-2'><StatusBadge status={row.state} /></td>
                  <td className='p-2'>{row.peak?.observed_rt?.toFixed(2) || '–'}</td>
                  <td className='p-2'>{row.peak?.apex_intensity ? row.peak.apex_intensity.toExponential(2) : '–'}</td>
                  <td className='p-2'>{row.peak?.signal_to_noise?.toFixed(1) || '–'}</td>
                  <td className='p-2'><StatusBadge status={row.peak?.quality_class || 'unknown'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit min-h-[300px]'>
          {selectedRow ? (
            <>
              <h3 className='text-[12px] font-semibold mb-2'>
                XIC — {selectedRow.target.compound_name} ({selectedRow.target.target_mz})
              </h3>
              <TicChart
                data={(selectedRow.xic || []).map((p) => ({ retention_time_minutes: p.retention_time_minutes, tic: p.intensity }))}
                sampleName={selectedRow.target.compound_name}
                height={240}
              />
              <div className='text-[10px] text-orbit-muted mt-2'>
                {selectedRow.xic ? `${selectedRow.xic.length.toLocaleString()} points` : 'Click row to load XIC'}
              </div>
            </>
          ) : (
            <div className='text-orbit-muted text-xs'>Select a target to view extracted ion chromatogram.</div>
          )}
        </div>
      </div>
    </div>
  );
}
