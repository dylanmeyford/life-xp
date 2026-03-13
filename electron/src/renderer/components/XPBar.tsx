import type { Stats } from '../types';

export default function XPBar({ stats }: { stats: Stats }) {
  return (
    <div className="bg-bg-card rounded-2xl p-6 border border-white/5 card-glow">
      <div className="flex items-center gap-4 mb-4">
        {/* Level Badge */}
        <div className="level-badge w-14 h-16 flex items-center justify-center">
          <span className="text-white font-bold text-lg">{stats.level}</span>
        </div>

        <div className="flex-1">
          <div className="flex items-baseline gap-2">
            <h2 className="text-xl font-bold text-white">{stats.title}</h2>
            <span className="text-sm text-white/40">Level {stats.level}</span>
          </div>
          <div className="text-accent-xp font-mono text-sm">
            {stats.total_xp.toLocaleString()} XP
          </div>
        </div>
      </div>

      {/* XP Progress Bar */}
      <div className="relative">
        <div className="h-3 bg-bg-primary rounded-full overflow-hidden xp-bar-glow">
          <div
            className="xp-fill h-full rounded-full"
            style={{ width: `${stats.progress_pct}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-xs text-white/40 font-mono">
            {stats.xp_in_level} / {stats.xp_for_next} XP
          </span>
          <span className="text-xs text-accent-primary font-mono">
            {stats.progress_pct.toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}
