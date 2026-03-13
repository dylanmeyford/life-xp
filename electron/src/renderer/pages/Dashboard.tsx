import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Stats, Habit } from '../types';
import XPBar from '../components/XPBar';
import DailyTasks from '../components/DailyTasks';
import Sparkline from '../components/Sparkline';
import HabitGrid from '../components/HabitGrid';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [habits, setHabits] = useState<Habit[]>([]);

  useEffect(() => {
    api.getStats().then(setStats);
    api.listHabits().then(setHabits);
  }, []);

  const checkHabit = async (id: number) => {
    await api.checkHabit(id);
    api.getStats().then(setStats);
    api.listHabits().then(setHabits);
  };

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-white/30 text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* XP Bar */}
      <XPBar stats={stats} />

      {/* Two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Tasks */}
        <DailyTasks />

        {/* Habits Quick Check */}
        <div className="bg-bg-card rounded-xl p-4 border border-white/5">
          <h3 className="text-sm font-semibold text-white mb-3">Habits</h3>
          {habits.length === 0 ? (
            <p className="text-white/30 text-sm">No habits yet.</p>
          ) : (
            <div className="space-y-2">
              {habits.map((h) => (
                <div key={h.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5">
                  <button
                    onClick={() => !h.done_today && checkHabit(h.id)}
                    className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all flex-shrink-0
                      ${h.done_today
                        ? 'bg-accent-success/20 border-accent-success text-accent-success'
                        : 'border-white/20 hover:border-accent-primary'
                      }`}
                    disabled={h.done_today}
                  >
                    {h.done_today && '✓'}
                  </button>
                  <span className="text-sm text-white flex-1">{h.title}</span>
                  {h.streak > 0 && (
                    <span className={`text-xs font-mono ${h.streak >= 7 ? 'streak-fire text-accent-streak' : 'text-white/40'}`}>
                      {h.streak >= 7 ? '🔥' : '⚡'} {h.streak}d
                    </span>
                  )}
                  <span className="text-xs font-mono text-accent-xp">+{h.xp_per_check}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Sparkline */}
      <Sparkline />

      {/* Habit Grids */}
      {habits.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-white mb-3">Habit Grids</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {habits.slice(0, 4).map((h) => (
              <HabitGrid key={h.id} habitId={h.id} title={h.title} weeks={20} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
