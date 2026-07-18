import { useMemo } from 'react';
import Plot from 'react-plotly.js';
import type { TicPoint } from '../types';

function cssVar(name: string, fallback: string) {
  if (typeof window === 'undefined') return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

interface TicChartProps {
  data: TicPoint[];
  sampleName?: string;
  live?: boolean;
  height?: number;
}

export default function TicChart({ data, sampleName: _sampleName, live: _live, height = 263 }: TicChartProps) {
  const x = data.map((p) => p.retention_time_minutes);
  const y = data.map((p) => p.tic);

  const layout = useMemo(() => {
    const muted = cssVar('--muted', '#64748b');
    const grid = cssVar('--grid', 'rgba(100,116,139,0.2)');
    return {
      margin: { l: 44, r: 8, t: 4, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: muted, size: 9 },
      xaxis: {
        title: { text: 'Retention Time (min)', font: { size: 9 } },
        gridcolor: grid,
        zeroline: false,
      },
      yaxis: {
        tickformat: '.1e',
        gridcolor: grid,
        zeroline: false,
      },
      showlegend: false,
    };
  }, []);

  return (
    <div style={{ height }}>
      <Plot
        data={[
          {
            x,
            y,
            type: 'scatter',
            mode: 'lines',
            line: { color: '#2f7df4', width: 1.7 },
            fill: 'tozeroy',
            fillcolor: 'rgba(47,125,244,0.05)',
            hovertemplate: 'RT %{x:.2f} min<br>TIC %{y:.2e}<extra></extra>',
          } as any,
        ]}
        layout={layout as any}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%', height: '100%' }}
        onError={(err: any) => console.error('TicChart Plotly error', err)}
      />
    </div>
  );
}
