import { useEffect, useMemo, useState } from 'react';
import api from '../api/client';
import AlertList from '../components/AlertList';
import KpiCard from '../components/KpiCard';
import PeakMonitor from '../components/PeakMonitor';
import SequenceQueue from '../components/SequenceQueue';
import StatusPanel from '../components/StatusPanel';
import TargetDonut from '../components/TargetDonut';
import TicChart from '../components/TicChart';
import useDashboard from '../hooks/useDashboard';
import useWebSocket from '../hooks/useWebSocket';
import type { PeakRow, Sample, TicPoint } from '../types';

const statusItems = [
  { name: 'Spray Voltage', value: '+3.45 kV' },
  { name: 'Sheath Gas (N2)', value: '35 arb' },
  { name: 'Aux Gas (N2)', value: '10 arb' },
  { name: 'Sweep Gas (N2)', value: '1 arb' },
  { name: 'Capillary Temp', value: '320 °C' },
  { name: 'S-Lens RF Level', value: '55 %' },
  { name: 'MS Pressure', value: '2.1e-6 mbar' },
  { name: 'Detector', value: '1.02e9 Counts' },
];

const dummyPeaks: PeakRow[] = [
  { compound_name: 'SAM', adduct: '[M+H]+', target_mz: 399.1448, status: 'Apex Detected', statusClass: 'green', rt: 6.39, expected_rt: 6.42, apex_intensity: 2840000, sn: 28.7, shape: 'Good', shapeClass: 'text-orbit-green', filter: 'good', color: '#3ecf66' },
  { compound_name: 'SAH', adduct: '[M+H]+', target_mz: 385.1292, status: 'Eluting', statusClass: 'blue', rt: 5.87, expected_rt: 5.88, apex_intensity: 1320000, sn: 17.8, shape: 'Good', shapeClass: 'text-orbit-green', filter: 'good', color: '#3b82f6' },
  { compound_name: 'Betaine', adduct: '[M+H]+', target_mz: 118.0864, status: 'Low Intensity', statusClass: 'yellow', rt: 4.82, expected_rt: 4.8, apex_intensity: 8210, sn: 2.3, shape: 'Poor', shapeClass: 'text-orbit-orange', filter: 'warning', color: '#f97316' },
  { compound_name: 'Citrate', adduct: '[M-H]-', target_mz: 191.0191, status: 'RT Shift', statusClass: 'orange', rt: 7.61, expected_rt: 7.19, apex_intensity: 412000, sn: 6.4, shape: 'OK', shapeClass: 'text-orbit-yellow', filter: 'warning', color: '#f4bf18' },
  { compound_name: 'Adenosine', adduct: '[M+H]+', target_mz: 268.1030, status: 'Not Detected', statusClass: 'red', rt: undefined, expected_rt: 4.55, apex_intensity: undefined, sn: undefined, shape: '–', shapeClass: '', filter: 'missing', color: '#7c8998' },
];

export default function Dashboard() {
  const { summary, tic, peaks, alerts, loading, setTic } = useDashboard();
  const [samples, setSamples] = useState<Sample[]>([]);

  useEffect(() => {
    if (summary?.current_sequence?.id) {
      api.get(`/sequences/${summary.current_sequence.id}/samples?limit=100`).then((res) => {
        setSamples(res.data.items);
      });
    }
  }, [summary?.current_sequence?.id]);

  const onMessage = (msg: any) => {
    if (msg.payload?.type === 'scan' && msg.payload.tic != null) {
      const point: TicPoint = {
        retention_time_minutes: msg.payload.retention_time_minutes,
        tic: msg.payload.tic,
        scan_number: msg.payload.scan_number,
      };
      setTic((prev) => [...prev, point]);
    }
    if (msg.payload?.type === 'sample.updated') {
      setSamples((prev) =>
        prev.map((s) => (s.id === msg.payload.sample_id ? { ...s, progress_pct: msg.payload.progress, acquisition_status: msg.payload.status } : s))
      );
    }
  };

  const channels = useMemo(() => {
    const list: string[] = [];
    if (summary?.current_sequence?.instrument_id) list.push(`instrument:${summary.current_sequence.instrument_id}`);
    if (summary?.current_sequence?.id) list.push(`sequence:${summary.current_sequence.id}`);
    if (summary?.current_sample?.id) list.push(`sample:${summary.current_sample.id}`);
    return list;
  }, [summary]);

  useWebSocket(onMessage, channels);

  if (loading) return <div className='p-10 text-orbit-muted'>Loading dashboard...</div>;

  return (
    <div>
      <section className='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-2.5'>
        <KpiCard kicker='Current Sample' subtext={`Type: ${summary?.current_sample?.sample_type || '—'} | Position: ${summary?.current_sample?.position || '—'}`}>
          <span>{summary?.current_sample?.sample_name || '—'}</span>
          <span className='ml-2 px-2 py-1 rounded text-[10px] font-bold bg-[rgba(43,134,229,0.15)] text-[#4f98ff]'>
            {summary?.current_sample?.acquisition_status || 'Idle'}
          </span>
        </KpiCard>

        <KpiCard kicker='Run Time' subtext={`of ${summary?.expected_run_time_min?.toFixed(2) || '—'} min`}>
          <span>{summary?.run_time_min?.toFixed(2) || '—'}</span>
          <span className='text-[10px] text-orbit-muted ml-1'>min</span>
          <div className='flex items-center gap-2.5 mt-3 w-full'>
            <div className='h-1 bg-orbit-deep rounded-full flex-1 overflow-hidden'>
              <div className='h-full bg-gradient-to-r from-[#2576ee] to-[#70a7ff] rounded-full' style={{ width: `${summary?.progress_pct || 0}%` }} />
            </div>
            <span className='text-[10px] text-orbit-muted'>{summary?.progress_pct || 0}%</span>
          </div>
        </KpiCard>

        <KpiCard kicker='RT (Live)' subtext={`${summary?.rt_live_min?.toFixed(3) || '—'} min`}>
          <span>{summary?.rt_live_min?.toFixed(3) || '—'}</span>
          <span className='text-[10px] text-orbit-muted ml-1'>min</span>
        </KpiCard>

        <KpiCard kicker='TIC (Live)' subtext='Total Ion Current'>
          <span>{summary?.tic_live ? summary.tic_live.toExponential(2) : '—'}</span>
        </KpiCard>

        <KpiCard kicker='Scan' subtext={`${summary?.current_sample?.method_name || '—'}`}>
          <span>{summary?.scan_number?.toLocaleString() || '—'}</span>
          <span className='ml-2 px-2 py-1 rounded text-[10px] font-bold bg-orbit-deep text-orbit-muted'>{summary?.ms_order || '—'}</span>
        </KpiCard>

        <KpiCard kicker='Polarity' subtext='+3.45 kV'>
          <span>{summary?.polarity || '—'}</span>
        </KpiCard>
      </section>

      <section className='grid grid-cols-1 xl:grid-cols-[1.25fr_0.72fr_0.69fr] gap-2.5 mt-2.5'>
        <article className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit min-h-[328px]'>
          <div className='flex items-start justify-between gap-3 mb-2'>
            <h2 className='text-[13px] font-semibold'>
              Total Ion Current (TIC)
              <span className='font-medium text-orbit-muted ml-1'>— {summary?.current_sample?.sample_name || '—'}</span>
              <span className='text-orbit-green text-[10px] ml-2'>● Live</span>
            </h2>
            <div className='flex gap-2'>
              <select className='h-[30px] px-2 rounded-md bg-orbit-soft border border-orbit-border text-orbit-text text-[10px]'>
                <option>1 min</option>
                <option>5 min</option>
                <option>Full run</option>
              </select>
              <button className='w-[30px] h-[30px] rounded-md border border-orbit-border bg-orbit-soft text-orbit-muted grid place-items-center hover:text-orbit-text'>⌕</button>
              <button className='w-[30px] h-[30px] rounded-md border border-orbit-border bg-orbit-soft text-orbit-muted grid place-items-center hover:text-orbit-text'>⛶</button>
            </div>
          </div>
          <TicChart data={tic} sampleName={summary?.current_sample?.sample_name} />
        </article>

        <StatusPanel items={statusItems} />

        <div className='grid gap-2.5'>
          <article className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit min-h-[205px]'>
            <h2 className='text-[13px] font-semibold mb-2'>Target Summary <span className='font-medium text-orbit-muted'>(This Sample)</span></h2>
            <div className='grid grid-cols-[145px_1fr] gap-2 items-center'>
              <TargetDonut summary={summary?.target_summary || {}} />
              <div className='grid gap-2 text-[10px]'>
                {[
                  { label: 'Detected', color: '#3ecf66' },
                  { label: 'Eluting', color: '#3b82f6' },
                  { label: 'Low Intensity', color: '#f4bf18' },
                  { label: 'Not Detected', color: '#f97316' },
                  { label: 'Outside Window', color: '#8b5cf6' },
                ].map((item) => (
                  <div key={item.label} className='flex items-center gap-2'>
                    <span className='w-2 h-2 rounded-full' style={{ background: item.color }} />
                    <span className='text-orbit-muted'>{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className='text-orbit-green text-[10px] mt-1'>Good peak shape in expected RT windows</div>
          </article>

          <article className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
            <div className='flex items-start justify-between mb-2'>
              <h2 className='text-[13px] font-semibold'>Recent Alerts</h2>
              <button className='text-[10px] text-[#4c91ff] bg-transparent border-0'>View All</button>
            </div>
            <AlertList alerts={alerts} />
          </article>
        </div>
      </section>

      <section className='grid grid-cols-1 xl:grid-cols-[0.78fr_1.32fr] gap-2.5 mt-2.5'>
        <SequenceQueue samples={samples.length ? samples : (summary?.current_sample ? [summary.current_sample] : []) as Sample[]} />
        <PeakMonitor peaks={peaks.length ? peaks : dummyPeaks} />
      </section>
    </div>
  );
}
