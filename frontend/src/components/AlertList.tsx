import type { AlertItem } from '../types';

const severityClass: Record<string, string> = {
  warning: 'bg-[rgba(244,191,24,0.07)]',
  error: 'bg-[rgba(249,115,22,0.07)]',
  info: 'bg-[rgba(43,134,229,0.07)]',
  critical: 'bg-[rgba(239,68,68,0.07)]',
};

const titleColor: Record<string, string> = {
  warning: 'text-orbit-yellow',
  error: 'text-orbit-orange',
  info: 'text-[#5297ff]',
  critical: 'text-orbit-red',
};

export default function AlertList({ alerts }: { alerts: AlertItem[] }) {
  if (!alerts.length) {
    return <div className='text-orbit-muted text-[10px] p-2'>No open alerts.</div>;
  }
  return (
    <div className='space-y-1'>
      {alerts.slice(0, 5).map((a) => (
        <div key={a.id} className={`grid grid-cols-[15px_1fr_auto] gap-2 items-start p-2 rounded text-[9px] ${severityClass[a.severity] || severityClass.info}`}>
          <span>{a.severity === 'warning' ? '⚠' : '●'}</span>
          <div>
            <div className={`font-bold ${titleColor[a.severity] || titleColor.info} mb-0.5`}>{a.category}</div>
            <div className='text-orbit-muted'>{a.message}</div>
          </div>
          <span className='text-orbit-muted whitespace-nowrap'>{new Date(a.last_seen_at).toLocaleTimeString()}</span>
        </div>
      ))}
    </div>
  );
}
