export default function LiveBadge({ connected, stale }: { connected: boolean; stale?: boolean }) {
  const color = connected ? (stale ? 'bg-orbit-yellow' : 'bg-orbit-green') : 'bg-orbit-red';
  const text = connected ? (stale ? 'Stale' : 'Live') : 'Disconnected';
  return (
    <span className='inline-flex items-center gap-2 text-[10px] font-semibold'>
      <span className={`w-2 h-2 rounded-full ${color} shadow-[0_0_0_4px_rgba(62,207,102,0.1)]`} />
      {text}
    </span>
  );
}
