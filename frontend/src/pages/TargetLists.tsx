import { useEffect, useRef, useState } from 'react';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import type { Instrument, TargetList } from '../types';

export default function TargetLists() {
  const [lists, setLists] = useState<TargetList[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [assignTarget, setAssignTarget] = useState<string>('');
  const [assignInstrument, setAssignInstrument] = useState<string>('');
  const [uploadName, setUploadName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchLists = () => api.get('/target-lists').then((res) => setLists(res.data || []));

  useEffect(() => {
    fetchLists();
    api.get('/instruments').then((res) => setInstruments(res.data || []));
  }, []);

  const upload = async () => {
    if (!file || !uploadName) return;
    const form = new FormData();
    form.append('file', file);
    form.append('name', uploadName);
    try {
      const res = await api.post('/target-lists/import', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSelected(res.data.id);
      setMessage('Target list imported.');
      fetchLists();
    } catch (err: any) {
      setMessage(err.response?.data?.error?.message || 'Import failed');
    }
  };

  const assign = async () => {
    if (!assignTarget || !assignInstrument) return;
    try {
      await api.post(`/target-lists/${assignTarget}/assign?instrument_id=${assignInstrument}`);
      setMessage('Target list assigned.');
      fetchLists();
    } catch (err: any) {
      setMessage(err.response?.data?.error?.message || 'Assignment failed');
    }
  };

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold mb-3'>Target Lists</h2>
        {message && <div className='mb-3 p-2 rounded text-[10px] bg-orbit-deep text-orbit-text'>{message}</div>}
        <div className='grid grid-cols-1 md:grid-cols-2 gap-3'>
          <div className='space-y-2'>
            <h3 className='text-[11px] font-semibold'>Import CSV / XLSX</h3>
            <input
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
              placeholder='List name'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
            <input
              ref={fileRef}
              type='file'
              accept='.csv,.xlsx,.xls'
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className='text-[11px] text-orbit-muted'
            />
            <button
              onClick={upload}
              disabled={!file || !uploadName}
              className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px] disabled:opacity-50'
            >
              Import
            </button>
          </div>
          <div className='space-y-2'>
            <h3 className='text-[11px] font-semibold'>Assign to Instrument</h3>
            <select
              value={assignTarget}
              onChange={(e) => setAssignTarget(e.target.value)}
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            >
              <option value=''>Select target list</option>
              {lists.map((tl) => (
                <option key={tl.id} value={tl.id}>{tl.name}</option>
              ))}
            </select>
            <select
              value={assignInstrument}
              onChange={(e) => setAssignInstrument(e.target.value)}
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            >
              <option value=''>Select instrument</option>
              {instruments.map((inst) => (
                <option key={inst.id} value={inst.id}>{inst.name}</option>
              ))}
            </select>
            <button
              onClick={assign}
              disabled={!assignTarget || !assignInstrument}
              className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px] disabled:opacity-50'
            >
              Assign
            </button>
          </div>
        </div>
      </div>

      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit overflow-auto'>
        <table className='w-full border-collapse min-w-[600px] text-[10px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Name</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Description</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Active Version</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Created</th>
            </tr>
          </thead>
          <tbody>
            {lists.map((tl) => (
              <tr
                key={tl.id}
                onClick={() => setSelected(tl.id)}
                className={`border-b border-orbit-border/5 hover:bg-orbit-hover cursor-pointer ${selected === tl.id ? 'bg-orbit-hover' : ''}`}
              >
                <td className='p-2'>{tl.name}</td>
                <td className='p-2 text-orbit-muted'>{tl.description || '–'}</td>
                <td className='p-2'>{tl.active_version_id ? <StatusBadge status='good' /> : <StatusBadge status='waiting' />}</td>
                <td className='p-2'>{new Date(tl.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
