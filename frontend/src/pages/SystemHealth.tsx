import { useEffect, useMemo, useState } from 'react';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import TicChart from '../components/TicChart';
import type { AgentInfo, Instrument, TelemetryPoint } from '../types';

const metricDisplayNames: Record<string, string> = {
  SprayVoltage: 'Spray Voltage',
  SheathGas: 'Sheath Gas',
  AuxGas: 'Aux Gas',
  SweepGas: 'Sweep Gas',
  CapillaryTemperature: 'Capillary Temp',
  SLensRFLevel: 'S-Lens RF Level',
  MsPressure: 'MS Pressure',
  DetectorCounts: 'Detector Counts',
};

export default function SystemHealth() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [telemetry, setTelemetry] = useState<TelemetryPoint[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);

  useEffect(() => {
    api.get('/instruments').then((res) => {
      setInstruments(res.data || []);
      if (res.data?.length === 1) setSelected(res.data[0].id);
    });
    api.get('/admin/agents').then((res) => setAgents(res.data || []));
  }, []);

  useEffect(() => {
    if (!selected) return;
    const fetch = () => {
      api.get(`/instruments/${selected}/telemetry?limit=500`).then((res) => setTelemetry(res.data || []));
    };
    fetch();
    const id = setInterval(fetch, 5000);
    return () => clearInterval(id);
  }, [selected]);

  const byMetric = useMemo(() => {
    const map: Record<string, TelemetryPoint[]> = {};
    telemetry.forEach((t) => {
      map[t.metric_name] = map[t.metric_name] || [];
      map[t.metric_name].push(t);
    });
    Object.values(map).forEach((arr) => arr.sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()));
    return map;
  }, [telemetry]);

  const instrument = instruments.find((i) => i.id === selected);

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <div className='flex flex-wrap items-center gap-3'>
          <h2 className='text-[13px] font-semibold'>System Health</h2>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          >
            <option value=''>Select instrument</option>
            {instruments.map((inst) => (
              <option key={inst.id} value={inst.id}>{inst.name}</option>
            ))}
          </select>
          {instrument && <StatusBadge status={instrument.status} />}
        </div>
      </div>

      <div className='grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2.5'>
        <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
          <h3 className='text-[12px] font-semibold mb-2'>Agents</h3>
          <div className='space-y-2'>
            {agents.map((agent) => (
              <div key={agent.id} className='text-[11px] flex justify-between'>
                <span className='text-orbit-muted'>{agent.hostname}</span>
                <StatusBadge status={agent.is_active ? 'running' : 'queued'} />
              </div>
            ))}
            {!agents.length && <div className='text-[10px] text-orbit-muted'>No agents registered.</div>}
          </div>
        </div>

        {Object.entries(byMetric).map(([metric, points]) => (
          <div key={metric} className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
            <div className='flex items-start justify-between mb-1'>
              <h3 className='text-[11px] font-semibold'>{metricDisplayNames[metric] || metric}</h3>
              <span className='text-[10px] text-orbit-muted'>
                {points[points.length - 1]?.metric_value.toFixed(2)} {points[points.length - 1]?.unit}
              </span>
            </div>
            <TicChart data={points.map((p) => ({ retention_time_minutes: new Date(p.recorded_at).getTime() / 60000, tic: p.metric_value }))} height={120} />
          </div>
        ))}
      </div>
    </div>
  );
}
