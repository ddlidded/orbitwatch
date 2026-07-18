import { useMemo } from 'react';
import Plot from 'react-plotly.js';

interface TargetDonutProps {
  summary: Record<string, number>;
}

function cssVar(name: string, fallback: string) {
  if (typeof window === 'undefined') return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

export default function TargetDonut({ summary }: TargetDonutProps) {
  const labels = ['Detected', 'Eluting', 'Low Intensity', 'Not Detected', 'Outside Window'];
  const values = [
    (summary['complete'] ?? 0) + (summary['detected'] ?? 0),
    (summary['eluting'] ?? 0) + (summary['apex_candidate'] ?? 0),
    summary['low_intensity'] ?? 0,
    summary['not_detected'] ?? 0,
    summary['outside_window'] ?? 0,
  ];
  const colors = ['#3ecf66', '#3b82f6', '#f4bf18', '#f97316', '#8b5cf6'];
  const total = summary['total'] ?? values.reduce((a, b) => a + b, 0);

  const layout = useMemo(() => ({
    margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    showlegend: false,
  }), []);

  return (
    <div className='h-[145px] w-[145px] relative'>
      <Plot
        data={[
          {
            values,
            labels,
            type: 'pie',
            hole: 0.64,
            sort: false,
            textinfo: 'none',
            marker: { colors, line: { color: cssVar('--panel', '#ffffff'), width: 1 } },
            hovertemplate: '%{label}: %{value}<extra></extra>',
          } as any,
        ]}
        layout={layout as any}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%', height: '100%' }}
        onError={(err: any) => console.error('TargetDonut Plotly error', err)}
      />
      <div className='absolute inset-0 grid place-content-center text-center pointer-events-none'>
        <b className='text-[22px]'>{total}</b>
        <span className='text-[10px] text-orbit-muted'>Targets</span>
      </div>
    </div>
  );
}
