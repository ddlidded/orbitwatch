import { useState } from 'react';
import api from '../api/client';

export default function InstrumentConnection() {
  const [form, setForm] = useState({
    name: '',
    serial_number: '',
    model: 'Orbitrap Exploris 480',
    api_version: '',
    tune_version: '',
    iapi_version: '',
  });
  const [result, setResult] = useState<{ agent_id: string; instrument_id: string; token: string } | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setResult(null);
    setLoading(true);
    try {
      const res = await api.post('/admin/instruments', form);
      setResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to register instrument');
    } finally {
      setLoading(false);
    }
  };

  const configSnippet = result
    ? `{
  "Agent": {
    "Mode": "helios",
    "BackendUrl": "${window.location.origin}",
    "AgentToken": "${result.token}",
    "AgentId": "${result.agent_id}",
    "InstrumentId": "${result.instrument_id}",
    "Instrument": {
      "Serial": "${form.serial_number}",
      "Name": "${form.name}",
      "Model": "${form.model}"
    }
  }
}`
    : '';

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold mb-2'>Connect Instrument</h2>
        <p className='text-[10px] text-orbit-muted mb-3'>
          Register a new Exploris 480 below to get an agent token. Copy the token and the JSON snippet into the OrbitWatch agent
          appsettings on the instrument PC. The agent will then authenticate directly and start streaming sequence and scan data.
        </p>
        <ol className='list-decimal list-inside text-[10px] text-orbit-muted space-y-1 mb-3'>
          <li>Install the OrbitWatch agent Windows service on the instrument PC.</li>
          <li>Paste the generated token and IDs into <code>appsettings.Production.json</code>.</li>
          <li>Set <code>Agent:Mode</code> to <code>helios</code> (or <code>replay</code> for testing).</li>
          <li>Ensure Thermo Tune/IAPI runtime is installed and the instrument is online.</li>
          <li>Start the agent service. It will connect securely over HTTPS and never accept inbound connections.</li>
        </ol>

        {error && <div className='mb-3 p-2 rounded text-[10px] bg-red-950 text-red-200'>{error}</div>}

        <form onSubmit={submit} className='grid grid-cols-1 md:grid-cols-2 gap-3 mb-3'>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Instrument Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder='e.g. Exploris 480 Lab 1'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
              required
            />
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Serial Number</label>
            <input
              value={form.serial_number}
              onChange={(e) => setForm({ ...form, serial_number: e.target.value })}
              placeholder='Instrument serial number'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
              required
            />
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Model</label>
            <input
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              placeholder='Orbitrap Exploris 480'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
              required
            />
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>API Version</label>
            <input
              value={form.api_version}
              onChange={(e) => setForm({ ...form, api_version: e.target.value })}
              placeholder='e.g. 3.8.0'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Tune Version</label>
            <input
              value={form.tune_version}
              onChange={(e) => setForm({ ...form, tune_version: e.target.value })}
              placeholder='e.g. 3.4.0'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>IAPI Version</label>
            <input
              value={form.iapi_version}
              onChange={(e) => setForm({ ...form, iapi_version: e.target.value })}
              placeholder='e.g. 3.8.0'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div className='md:col-span-2'>
            <button type='submit' disabled={loading} className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px]'>
              {loading ? 'Registering...' : 'Register Instrument'}
            </button>
          </div>
        </form>

        {result && (
          <div className='p-3 rounded-md border border-orbit-border bg-orbit-deep'>
            <div className='text-[11px] font-semibold mb-2'>Agent token generated</div>
            <div className='text-[10px] text-orbit-muted mb-1'>Copy this into the agent config on the instrument PC:</div>
            <pre className='p-2 rounded bg-orbit-bg text-[10px] text-orbit-text overflow-auto whitespace-pre-wrap break-all'>{configSnippet}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
