import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Sparkline({ days = 30 }: { days?: number }) {
  const [data, setData] = useState<{ day: string; xp: number }[]>([]);

  useEffect(() => {
    api.getXPHistory(days).then(setData);
  }, [days]);

  if (data.length === 0) return null;

  const max = Math.max(...data.map(d => d.xp), 1);
  const total = data.reduce((sum, d) => sum + d.xp, 0);
  const barWidth = Math.max(2, Math.floor(200 / data.length) - 1);

  return (
    <div className="bg-bg-card rounded-xl p-4 border border-white/5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">XP Activity</h3>
        <span className="text-xs font-mono text-accent-xp">{total.toLocaleString()} XP</span>
      </div>

      <div className="flex items-end gap-[1px] h-12">
        {data.map((d, i) => {
          const height = Math.max(2, (d.xp / max) * 48);
          return (
            <div
              key={i}
              className="bg-accent-success/60 rounded-t-sm hover:bg-accent-success transition-colors"
              style={{ width: `${barWidth}px`, height: `${height}px` }}
              title={`${d.day}: +${d.xp} XP`}
            />
          );
        })}
      </div>

      <div className="flex justify-between mt-1">
        <span className="text-[10px] text-white/20">{data[0]?.day}</span>
        <span className="text-[10px] text-white/20">{data[data.length - 1]?.day}</span>
      </div>
    </div>
  );
}
