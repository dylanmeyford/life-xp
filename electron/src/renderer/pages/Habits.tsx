import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Habit } from '../types';
import HabitGrid from '../components/HabitGrid';

export default function Habits() {
  const [habits, setHabits] = useState<Habit[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: '', category: 'Productivity', frequency: 'daily', xp_per_check: 25,
  });

  const loadHabits = () => api.listHabits().then(setHabits);
  useEffect(() => { loadHabits(); }, []);

  const createHabit = async () => {
    await api.createHabit(form);
    setShowCreate(false);
    setForm({ title: '', category: 'Productivity', frequency: 'daily', xp_per_check: 25 });
    loadHabits();
  };

  const checkHabit = async (id: number) => {
    await api.checkHabit(id);
    loadHabits();
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">🔥 Habits</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-accent-streak/20 text-accent-streak rounded-lg hover:bg-accent-streak/30 transition text-sm font-medium"
        >
          + New Habit
        </button>
      </div>

      {showCreate && (
        <div className="bg-bg-card rounded-xl p-6 border border-white/5 mb-6 space-y-4">
          <input
            className="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-streak focus:outline-none"
            placeholder="Habit name (e.g. Meditate, Exercise, Read)"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div className="grid grid-cols-3 gap-4">
            <select
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white"
              value={form.frequency}
              onChange={(e) => setForm({ ...form, frequency: e.target.value })}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
            <select
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              {['Fitness','Finance','Social','Learning','Productivity','Creative','Health','Mindfulness'].map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <input
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white"
              type="number"
              placeholder="XP per check"
              value={form.xp_per_check}
              onChange={(e) => setForm({ ...form, xp_per_check: Number(e.target.value) })}
            />
          </div>
          <div className="flex gap-3">
            <button onClick={createHabit} disabled={!form.title} className="px-6 py-2 bg-accent-streak text-black font-semibold rounded-lg hover:bg-accent-streak/80 transition disabled:opacity-30">
              Create Habit
            </button>
            <button onClick={() => setShowCreate(false)} className="px-6 py-2 text-white/40 hover:text-white transition">Cancel</button>
          </div>
        </div>
      )}

      {/* Habit List */}
      <div className="space-y-3 mb-8">
        {habits.map((h) => (
          <div key={h.id} className="bg-bg-card rounded-xl p-4 border border-white/5 card-glow">
            <div className="flex items-center gap-3">
              <button
                onClick={() => !h.done_today && checkHabit(h.id)}
                className={`w-6 h-6 rounded-lg border-2 flex items-center justify-center transition-all flex-shrink-0
                  ${h.done_today
                    ? 'bg-accent-success/20 border-accent-success text-accent-success'
                    : 'border-white/20 hover:border-accent-streak hover:bg-accent-streak/10'
                  }`}
                disabled={h.done_today}
              >
                {h.done_today && '✓'}
              </button>
              <span className="text-lg">{h.category_icon || '⭐'}</span>
              <span className="text-white font-medium flex-1">{h.title}</span>
              <span className="text-xs text-white/30">{h.frequency}</span>
              {h.streak > 0 && (
                <span className={`text-sm font-mono font-bold ${h.streak >= 7 ? 'streak-fire text-accent-streak' : 'text-white/50'}`}>
                  {h.streak >= 7 ? '🔥' : '⚡'} {h.streak}d
                </span>
              )}
              <span className="text-sm font-mono text-accent-xp">+{h.xp_per_check}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Contribution Grids */}
      {habits.length > 0 && (
        <div>
          <h2 className="text-lg font-bold mb-4">Contribution Grids</h2>
          <div className="grid grid-cols-1 gap-4">
            {habits.map((h) => (
              <HabitGrid key={h.id} habitId={h.id} title={h.title} weeks={52} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
