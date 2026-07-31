import React, { useEffect, useState } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Scale } from 'lucide-react';

function getHeatmapColor(mean) {
  const t = Math.max(0, Math.min(1, (mean - 1) / 2));
  const r = Math.round(6 + (168 - 6) * t);
  const g = Math.round(182 + (85 - 182) * t);
  const b = Math.round(212 + (247 - 212) * t);
  return `rgba(${r}, ${g}, ${b}, 0.8)`;
}

function getHeatmapGlow(mean) {
  const t = Math.max(0, Math.min(1, (mean - 1) / 2));
  const r = Math.round(6 + (168 - 6) * t);
  const g = Math.round(182 + (85 - 182) * t);
  const b = Math.round(212 + (247 - 212) * t);
  return `0 0 ${10 + t * 20}px rgba(${r}, ${g}, ${b}, ${0.5 + t * 0.5})`;
}

const CustomShape = (props) => {
  const { cx, cy, payload } = props;
  
  if (payload.suppressed) {
    return (
      <g>
        <rect x={cx - 30} y={cy - 20} width={60} height={40} fill="rgba(255,255,255,0.03)" rx={6} stroke="rgba(255,255,255,0.05)" />
        <text x={cx} y={cy} dy={4} textAnchor="middle" fill="var(--color-text-muted)" fontSize="12" fontFamily="monospace">n &lt; k</text>
      </g>
    );
  }

  const fill = getHeatmapColor(payload.mean_difficulty);
  const glow = getHeatmapGlow(payload.mean_difficulty);
  
  return (
    <g>
      <rect x={cx - 30} y={cy - 20} width={60} height={40} fill={fill} rx={6} style={{ filter: `drop-shadow(${glow})` }} />
      <text x={cx} y={cy} dy={4} textAnchor="middle" fill="#fff" fontSize="13" fontWeight="bold">
        {payload.mean_difficulty.toFixed(2)}
      </text>
    </g>
  );
};

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="glass-panel p-3 bg-[rgba(9,9,11,0.9)] border border-[var(--color-glass-border-strong)]">
        <p className="text-[var(--color-text-secondary)] mb-1 text-sm">{data.dimension} : {data.value}</p>
        {data.suppressed ? (
          <p className="text-[var(--color-text-muted)] text-sm">Suppressed (n &lt; k)</p>
        ) : (
          <>
            <p className="text-white font-bold text-sm">Difficulty: {data.mean_difficulty.toFixed(2)}</p>
            <p className="text-[var(--color-text-muted)] text-xs mt-1">Samples: {data.n}</p>
          </>
        )}
      </div>
    );
  }
  return null;
};

export default function FairnessHeatmap({ roleId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
    fetch(`${apiBase}/api/fairness/heatmap?role_id=${encodeURIComponent(roleId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setData)
      .catch((e) => setError(e.message));
  }, [roleId]);

  if (error) return (
    <div className="glass-panel glass-panel-purple p-6 flex items-center gap-3 text-rose-500 h-full">
      <span>⚠️</span> Fairness Lens Error: {error}
    </div>
  );
  
  if (!data) return (
    <div className="glass-panel glass-panel-purple p-6 flex items-center justify-center h-full text-[var(--color-text-muted)] font-mono text-sm gap-3">
      <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse"></div>
      Aggregating telemetry...
    </div>
  );

  const dimensions = [...new Set(data.cells.map(c => c.dimension))];
  const cohorts = [...new Set(data.cells.map(c => c.value))];
  
  const chartData = data.cells.map(c => ({
    ...c,
    x: cohorts.indexOf(c.value),
    y: dimensions.indexOf(c.dimension),
    z: c.suppressed ? 0 : c.mean_difficulty
  }));

  return (
    <div className="glass-panel glass-panel-purple flex flex-col h-full overflow-hidden">
      <div className="flex items-center gap-3 p-4 border-b border-[var(--color-glass-border)] bg-[rgba(255,255,255,0.02)]">
        <div className="w-10 h-10 rounded-xl bg-[var(--color-glass-hover)] border border-[var(--color-glass-border-strong)] flex items-center justify-center text-purple-400 shadow-[0_0_10px_rgba(168,85,247,0.2)]">
          <Scale size={20} />
        </div>
        <div>
          <h3 className="text-base font-medium">Fairness & Bias Lens</h3>
          <span className="text-[11px] font-mono text-purple-400 tracking-wider">K-ANONYMIZED COHORTS</span>
        </div>
      </div>

      <div className="flex-1 p-6 flex flex-col">
        {data.drift_alerts.length > 0 && (
          <div className="bg-[rgba(245,158,11,0.1)] border border-[rgba(245,158,11,0.2)] rounded-lg p-4 mb-6 shadow-[0_0_15px_rgba(245,158,11,0.15)]">
            <div className="flex items-center gap-2 text-amber-500 font-medium mb-2 text-sm">
              <span>⚠️</span> Active Drift Detected
            </div>
            {data.drift_alerts.map((a, i) => (
              <div key={i} className="text-xs text-[var(--color-text-secondary)]">
                <strong className="text-white">{a.dimension}={a.value}</strong> · Mean {a.mean_difficulty.toFixed(2)} vs baseline {a.overall_mean.toFixed(2)}
              </div>
            ))}
          </div>
        )}

        <div className="flex-1 min-h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 60 }}>
              <XAxis type="number" dataKey="x" name="Cohort" domain={[0, cohorts.length - 1]} 
                     tickFormatter={v => cohorts[v]} tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }} 
                     axisLine={false} tickLine={false} />
              <YAxis type="number" dataKey="y" name="Dimension" domain={[0, dimensions.length - 1]} 
                     tickFormatter={v => dimensions[v]} tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
                     axisLine={false} tickLine={false} />
              <ZAxis dataKey="z" range={[0, 100]} />
              <Tooltip cursor={{ strokeDasharray: '3 3', stroke: 'var(--color-glass-border)' }} content={<CustomTooltip />} />
              <Scatter data={chartData} shape={<CustomShape />} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 pt-4 border-t border-[var(--color-glass-border)] flex justify-between items-center text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm" style={{ background: getHeatmapColor(1), boxShadow: getHeatmapGlow(1) }}></div>
            <span className="text-[var(--color-text-muted)]">Easier</span>
            <div className="w-3 h-3 rounded-sm ml-3" style={{ background: getHeatmapColor(3), boxShadow: getHeatmapGlow(3) }}></div>
            <span className="text-[var(--color-text-muted)]">Harder</span>
          </div>
          <div className="text-[var(--color-text-muted)]">
            Baseline: <span className="text-white font-mono">{data.overall_mean.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
