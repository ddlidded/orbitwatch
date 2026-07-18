import { useEffect, useState } from 'react';
import api from '../api/client';
import PeakMonitor from '../components/PeakMonitor';
import type { Instrument, PeakRow } from '../types';

export default function PeakMonitorPage() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [selectedInstrument, setSelectedInstrument] = useState<string>('');
  const [peaks, setPeaks] = useState<PeakRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/instruments').then((res) => {
      setInstruments(res.data || []);
      if (res.data?.length === 1) setSelectedInstrument(res.data[0].id);
    });
  }, []);

  useEffect(() => {
    const fetch = () => {
      const url = selectedInstrument ? `/dashboard/peak-monitor?instrument_id=${selectedInstrument}` : '/dashboard/peak-monitor';
      api.get(url).then((res) => setPeaks(res.data || [])).finally(() => setLoading(false));
    };
    fetch();
    const id = setInterval(fetch, 5000);
    return () => clearInterval(id);
  }, [selectedInstrument]);

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <div className='flex flex-wrap items-center justify-between gap-3'>
          <h2 className='text-[13px] font-semibold'>Peak Monitor</h2>
          <select
            value={selectedInstrument}
            onChange={(e) => setSelectedInstrument(e.target.value)}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          >
            <option value=''>Default instrument</option>
            {instruments.map((inst) => (
              <option key={inst.id} value={inst.id}>{inst.name} ({inst.serial_number})</option>
            ))}
          </select>
        </div>
      </div>
      {loading && <div className='text-orbit-muted text-xs'>Loading peaks…</div>}
      <PeakMonitor peaks={peaks} />
    </div>
  );
}
