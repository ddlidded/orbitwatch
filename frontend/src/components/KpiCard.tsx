import type { ReactNode } from 'react';

interface KpiCardProps {
  kicker: string;
  children: ReactNode;
  subtext?: string;
}

export default function KpiCard({ kicker, children, subtext }: KpiCardProps) {
  return (
    <article className='min-h-[102px] p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
      <div className='text-[10px] text-orbit-muted mb-2.5 font-medium'>{kicker}</div>
      <div className='flex items-center gap-2 text-xl font-semibold tracking-tight'>{children}</div>
      {subtext && <div className='text-[10px] text-orbit-muted mt-2'>{subtext}</div>}
    </article>
  );
}
