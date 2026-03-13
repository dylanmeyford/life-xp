import { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';

interface TrayData {
  stats: {
    total_xp: number;
    level: number;
    xp_in_level: number;
    xp_for_next: number;
    progress_pct: number;
    title: string;
  };
  goals: {
    id: number;
    title: string;
    category_icon: string;
    goal_type: string;
    progress: number | null;
    target_value: number | null;
    current_value: number | null;
    unit: string | null;
    recurrence: string | null;
  }[];
  habits: {
    id: number;
    title: string;
    category_icon: string;
    done_today: boolean;
    streak: number;
    xp_per_check: number;
  }[];
  daily_tasks: {
    done: number;
    total: number;
    items: {
      id: number;
      title: string;
      status: string;
      xp_reward: number;
    }[];
  };
}

interface InputResult {
  intent: string;
  reply: string;
  data: any;
}

export default function TrayDashboard() {
  const [data, setData] = useState<TrayData | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<InputResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = () => api.getTrayData().then(setData).catch(() => {});
  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    setLoading(true);
    setResult(null);
    try {
      const res = await api.smartInput(input.trim());
      setResult(res);
      setInput('');
      // Refresh data after action
      setTimeout(load, 500);
    } catch (err: any) {
      setResult({ intent: 'error', reply: err.message, data: {} });
    }
    setLoading(false);
  };

  const checkHabit = async (id: number) => {
    try {
      await api.checkHabit(id);
      load();
    } catch {}
  };

  const completeTask = async (id: number) => {
    try {
      await api.completeDailyTask(id);
      load();
    } catch {}
  };

  if (!data) {
    return (
      <div className="tray-container flex items-center justify-center h-full">
        <div className="text-white/30 text-sm">Connecting...</div>
      </div>
    );
  }

  const { stats, goals, habits, daily_tasks } = data;

  return (
    <div className="tray-container flex flex-col h-screen bg-[#0d0d14] overflow-hidden rounded-xl border border-white/10">
      {/* XP Header */}
      <div className="px-4 pt-3 pb-2 border-b border-white/5">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-accent-level/20 flex items-center justify-center text-accent-level text-xs font-bold">
              {stats.level}
            </div>
            <div>
              <div className="text-xs font-semibold text-white">{stats.title}</div>
              <div className="text-[10px] text-white/40">{stats.total_xp.toLocaleString()} XP</div>
            </div>
          </div>
          <div className="text-[10px] text-white/30">
            {stats.xp_in_level}/{stats.xp_for_next}
          </div>
        </div>
        <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-accent-primary to-accent-xp rounded-full transition-all duration-500"
            style={{ width: `${stats.progress_pct}%` }}
          />
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-3 tray-scroll">
        {/* Daily Tasks */}
        {daily_tasks.total > 0 && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-semibold text-white/50 uppercase tracking-wider">Today</span>
              <span className="text-[10px] text-accent-xp font-mono">{daily_tasks.done}/{daily_tasks.total}</span>
            </div>
            <div className="space-y-1">
              {daily_tasks.items.map((t) => (
                <button
                  key={t.id}
                  onClick={() => t.status === 'pending' && completeTask(t.id)}
                  disabled={t.status !== 'pending'}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5 transition text-left"
                >
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 text-[8px]
                    ${t.status === 'done'
                      ? 'bg-accent-success/20 border-accent-success text-accent-success'
                      : 'border-white/20'
                    }`}>
                    {t.status === 'done' && '✓'}
                  </div>
                  <span className={`text-xs flex-1 ${t.status === 'done' ? 'line-through text-white/25' : 'text-white/80'}`}>
                    {t.title}
                  </span>
                  <span className="text-[9px] font-mono text-accent-xp/50">+{t.xp_reward}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Habits */}
        {habits.length > 0 && (
          <div>
            <span className="text-[10px] font-semibold text-white/50 uppercase tracking-wider">Habits</span>
            <div className="mt-1.5 space-y-1">
              {habits.map((h) => (
                <button
                  key={h.id}
                  onClick={() => !h.done_today && checkHabit(h.id)}
                  disabled={h.done_today}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5 transition text-left"
                >
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 text-[8px]
                    ${h.done_today
                      ? 'bg-accent-success/20 border-accent-success text-accent-success'
                      : 'border-white/20 hover:border-accent-streak'
                    }`}>
                    {h.done_today && '✓'}
                  </div>
                  <span className="text-xs">{h.category_icon}</span>
                  <span className={`text-xs flex-1 ${h.done_today ? 'text-white/25' : 'text-white/80'}`}>{h.title}</span>
                  {h.streak > 0 && (
                    <span className={`text-[9px] font-mono ${h.streak >= 7 ? 'text-accent-streak' : 'text-white/30'}`}>
                      {h.streak >= 7 ? '🔥' : '⚡'}{h.streak}d
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Goals */}
        {goals.length > 0 && (
          <div>
            <span className="text-[10px] font-semibold text-white/50 uppercase tracking-wider">Goals</span>
            <div className="mt-1.5 space-y-1.5">
              {goals.map((g) => (
                <div key={g.id} className="px-2 py-1.5 rounded-lg hover:bg-white/5 transition">
                  <div className="flex items-center gap-2">
                    <span className="text-xs">{g.category_icon}</span>
                    <span className="text-xs text-white/80 flex-1 truncate">{g.title}</span>
                    {g.recurrence && (
                      <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-accent-primary/10 text-accent-primary/60">
                        {g.recurrence}
                      </span>
                    )}
                  </div>
                  {g.progress !== null && (
                    <div className="mt-1 h-1 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-primary/60 rounded-full"
                        style={{ width: `${g.progress * 100}%` }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {goals.length === 0 && habits.length === 0 && daily_tasks.total === 0 && (
          <div className="text-center py-8 text-white/20">
            <div className="text-2xl mb-2">✨</div>
            <p className="text-xs">Type below to add a goal or habit</p>
          </div>
        )}
      </div>

      {/* Agent response */}
      {result && (
        <div className="px-4 py-2 border-t border-white/5">
          <div className={`text-xs px-3 py-2 rounded-lg ${
            result.intent === 'error' ? 'bg-red-500/10 text-red-400' : 'bg-accent-primary/10 text-accent-primary'
          }`}>
            {result.reply}
          </div>
        </div>
      )}

      {/* Smart input */}
      <form onSubmit={handleSubmit} className="px-3 py-3 border-t border-white/5">
        <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={loading ? 'Thinking...' : 'Type anything... goals, check-ins, questions'}
            disabled={loading}
            className="flex-1 bg-transparent text-xs text-white placeholder-white/25 focus:outline-none disabled:opacity-50"
            autoFocus
          />
          {loading && (
            <div className="w-3 h-3 border-2 border-accent-primary/40 border-t-accent-primary rounded-full animate-spin" />
          )}
          {!loading && input.trim() && (
            <button type="submit" className="text-accent-primary text-xs font-medium hover:text-accent-primary/80">
              ↵
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
