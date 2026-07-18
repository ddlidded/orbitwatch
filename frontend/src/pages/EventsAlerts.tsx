import { useEffect, useState } from 'react';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import type { AlertItem, Instrument } from '../types';

export default function EventsAlerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [instrumentId, setInstrumentId] = useState<string>('');
  const [severity, setSeverity] = useState<string>('');
  const [status, setStatus] = useState<string>('open');

  useEffect(() => {
    api.get('/instruments').then((res) => setInstruments(res.data || []));
  }, []);

  const fetch = () => {
    const params = new URLSearchParams();
    if (instrumentId) params.set('instrument_id', instrumentId);
    if (severity) params.set('severity', severity);
    if (status) params.set('status', status);
    api.get(`/alerts?${params.toString()}`).then((res) => setAlerts(res.data.items || []));
  };

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, 10000);
    return () => clearInterval(interval);
  }, [instrumentId, severity, status]);

  const acknowledge = async (id: string) => {
    try {
      await api.post(`/alerts/${id}/acknowledge`, { notes: 'Acknowledged from UI' });
      fetch();
    } catch (err: any) {
      console.error(err);
    }
  };

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <div className='flex flex-wrap items-end gap-3'>
          <h2 className='text-[13px] font-semibold'>Events & Alerts</h2>
          <select value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)} className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'>
            <option value=''>All instruments</option>
            {instruments.map((i) => (<option key={i.id} value={i.id}>{i.name}</option>))}
          </select>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'>
            <option value=''>All severities</option>
            <option value='info'>Info</option>
            <option value='warning'>Warning</option>
            <option value='error'>Error</option>
            <option value='critical'>Critical</option>
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'>
            <option value=''>All statuses</option>
            <option value='open'>Open</option>
            <option value='acknowledged'>Acknowledged</option>
          </select>
        </div>
      </div>

      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit overflow-auto'>
        <table className='w-full border-collapse min-w-[700px] text-[10px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Time</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Category</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Severity</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Message</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Status</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'></th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} className='border-b border-orbit-border/5 hover:bg-orbit-hover'>
                <td className='p-2 whitespace-nowrap'>{new Date(a.last_seen_at).toLocaleString()}</td>
                <td className='p-2'>{a.category}</td>
                <td className='p-2'><StatusBadge status={a.severity} /></td>
                <td className='p-2'>{a.message}</td>
                <td className='p-2'><StatusBadge status={a.status} /></td>
                <td className='p-2'>
                  {a.status === 'open' && (
                    <button onClick={() => acknowledge(a.id)} className='h-[24px] px-2 rounded bg-orbit-blue text-white text-[9px]'>Ack</button>
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
