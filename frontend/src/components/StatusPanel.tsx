import { useEffect, useRef } from 'react';

interface StatusItem {
  name: string;
  value: string;
}

function MiniChart(values: number[], color: string) {
  // Canvas sparkline used in status rows.
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvasRef.current;
    if (!c || values.length < 2) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    c.width = Math.max(1, rect.width * dpr);
    c.height = Math.max(1, rect.height * dpr);
    const ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    const max = Math.max(...values, 1);
    values.forEach((v, i) => {
      const px = (i / (values.length - 1)) * rect.width;
      const py = rect.height - (v / max) * rect.height * 0.75 - rect.height * 0.1;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
  }, [values, color]);
  return <canvas ref={canvasRef} className='w-[91px] h-[18px]' />;
}

export default function StatusPanel({ items }: { items: StatusItem[] }) {
  return (
    <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit h-full'>
      <div className='flex items-start justify-between mb-2'>
        <h2 className='text-[13px] font-semibold'>Sample Status</h2>
        <span className='inline-flex items-center px-1.5 py-1 rounded text-[8px] font-bold text-[#69d95d] bg-[rgba(57,181,74,0.12)]'>Acquiring</span>
      </div>
      <div id='statusRows' className='space-y-0'>
        {items.map((item, i) => (
          <div key={item.name} className='grid grid-cols-[1fr_auto_91px] gap-2.5 items-center py-1.5 border-b border-orbit-border/5 text-[10px]'>
            <div className='flex items-center gap-2 text-orbit-muted'>
              <span className='text-orbit-green'>◉</span>
              {item.name}
            </div>
            <div>{item.value}</div>
            {MiniChart(
              Array.from({ length: 42 }, (_, j) => 0.35 + Math.sin((j + i) / 7) * 0.08 + Math.random() * 0.18),
              i === 3 ? '#89dc3c' : '#3ecf66'
            )}
          </div>
        ))}
      </div>
      <div className='flex items-center gap-2 mt-2.5 p-2 rounded bg-[rgba(44,170,74,0.12)] text-[#7ae454] text-[10px]'>
        <span>✓</span> All systems nominal
      </div>
    </div>
  );
}
