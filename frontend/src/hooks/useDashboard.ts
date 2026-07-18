import { useEffect, useState } from 'react';
import api from '../api/client';
import type { AlertItem, DashboardSummary, Instrument, PeakRow, TicPoint } from '../types';

export default function useDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [tic, setTic] = useState<TicPoint[]>([]);
  const [peaks, setPeaks] = useState<PeakRow[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    try {
      const [instRes, summaryRes, peaksRes, alertsRes] = await Promise.all([
        api.get('/instruments'),
        api.get('/dashboard/summary'),
        api.get('/dashboard/peak-monitor'),
        api.get('/alerts?status=open&limit=5'),
      ]);
      setInstruments(instRes.data);
      setSummary(summaryRes.data);
      setPeaks(peaksRes.data);
      setAlerts(alertsRes.data.items || []);
      if (summaryRes.data.current_sample?.id) {
        const ticRes = await api.get(`/samples/${summaryRes.data.current_sample.id}/tic?limit=10000`);
        setTic(ticRes.data.items);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 5000);
    return () => clearInterval(id);
  }, []);

  return { summary, instruments, tic, peaks, alerts, loading, setTic, setSummary, setAlerts };
}
