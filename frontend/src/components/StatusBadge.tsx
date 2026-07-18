const map: Record<string, string> = {
  completed: 'text-[#69d95d] bg-[rgba(57,181,74,0.12)]',
  running: 'text-[#65a8ff] bg-[rgba(43,134,229,0.13)]',
  queued: 'text-orbit-muted bg-orbit-deep',
  failed: 'text-[#ff6d61] bg-[rgba(239,68,68,0.13)]',
  warning: 'text-[#f4bf18] bg-[rgba(244,191,24,0.13)]',
  good: 'text-[#3ecf66] bg-[rgba(62,207,102,0.12)]',
  detected: 'text-[#3ecf66] bg-[rgba(62,207,102,0.12)]',
  waiting: 'text-orbit-muted bg-orbit-deep',
  missing: 'text-[#f97316] bg-[rgba(249,115,22,0.13)]',
  unknown: 'text-orbit-muted bg-orbit-deep',
  idle: 'text-orbit-muted bg-orbit-deep',
  acquiring: 'text-[#65a8ff] bg-[rgba(43,134,229,0.13)]',
  apex_candidate: 'text-[#3ecf66] bg-[rgba(62,207,102,0.12)]',
  finalized: 'text-[#69d95d] bg-[rgba(57,181,74,0.12)]',
  open: 'text-[#f4bf18] bg-[rgba(244,191,24,0.13)]',
  acknowledged: 'text-orbit-muted bg-orbit-deep',
  critical: 'text-[#ff6d61] bg-[rgba(239,68,68,0.13)]',
  info: 'text-[#65a8ff] bg-[rgba(43,134,229,0.13)]',
  orange: 'text-[#ff9c54] bg-[rgba(249,115,22,0.13)]',
  red: 'text-[#ff6d61] bg-[rgba(239,68,68,0.13)]',
  green: 'text-[#69d95d] bg-[rgba(57,181,74,0.12)]',
  blue: 'text-[#65a8ff] bg-[rgba(43,134,229,0.13)]',
};

export default function StatusBadge({ status, className = '' }: { status: string; className?: string }) {
  const cls = map[status.toLowerCase()] || map.queued;
  return (
    <span className={`inline-flex items-center px-1.5 py-1 rounded text-[8px] font-bold ${cls} ${className}`}>
      {status}
    </span>
  );
}
