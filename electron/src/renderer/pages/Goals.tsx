import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Goal, TrackingStrategy } from '../types';

export default function Goals() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: '', description: '', category: 'Productivity',
    xp_reward: 100, goal_type: 'manual', target_value: '',
    unit: '', due_date: '', recurrence: '',
  });

  // Sensor strategy selection state
  const [strategyGoalId, setStrategyGoalId] = useState<number | null>(null);
  const [strategies, setStrategies] = useState<TrackingStrategy[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(false);
  const [selectingStrategy, setSelectingStrategy] = useState(false);

  const loadGoals = () => api.listGoals().then(setGoals);
  useEffect(() => { loadGoals(); }, []);

  const createGoal = async () => {
    const result = await api.createGoal({
      ...form,
      xp_reward: Number(form.xp_reward),
      target_value: form.target_value ? Number(form.target_value) : null,
      unit: form.unit || null,
      due_date: form.due_date || null,
      recurrence: form.recurrence || null,
    });
    setShowCreate(false);
    setForm({ title: '', description: '', category: 'Productivity', xp_reward: 100, goal_type: 'manual', target_value: '', unit: '', due_date: '', recurrence: '' });
    loadGoals();

    // For non-manual goals, offer tracking strategy selection
    if (form.goal_type !== 'manual' && result?.id) {
      proposeStrategies(result.id);
    }
  };

  const proposeStrategies = async (goalId: number) => {
    setStrategyGoalId(goalId);
    setLoadingStrategies(true);
    try {
      const res = await api.proposeTracking(goalId);
      setStrategies(res.strategies || []);
    } catch {
      setStrategies([]);
    }
    setLoadingStrategies(false);
  };

  const selectStrategy = async (index: number) => {
    if (!strategyGoalId) return;
    setSelectingStrategy(true);
    try {
      await api.selectStrategy(strategyGoalId, index);
      setStrategyGoalId(null);
      setStrategies([]);
      loadGoals();
    } catch (err: any) {
      alert(err.message);
    }
    setSelectingStrategy(false);
  };

  const completeGoal = async (id: number) => {
    await api.completeGoal(id);
    loadGoals();
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">🎯 Goals</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-accent-primary/20 text-accent-primary rounded-lg hover:bg-accent-primary/30 transition text-sm font-medium"
        >
          + New Goal
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="bg-bg-card rounded-xl p-6 border border-white/5 mb-6 space-y-4">
          <input
            className="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-primary focus:outline-none"
            placeholder="What do you want to achieve?"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <textarea
            className="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-primary focus:outline-none resize-none"
            placeholder="Description (optional)"
            rows={2}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-4">
            <select
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white focus:border-accent-primary focus:outline-none"
              value={form.goal_type}
              onChange={(e) => setForm({ ...form, goal_type: e.target.value })}
            >
              <option value="manual">Manual Check-in</option>
              <option value="quantitative">Quantitative (with target)</option>
              <option value="qualitative">Qualitative (AI-tracked)</option>
              <option value="recurring">Recurring (daily/weekly)</option>
            </select>
            <select
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white focus:border-accent-primary focus:outline-none"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              {['Fitness','Finance','Social','Learning','Productivity','Creative','Health','Mindfulness'].map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          {form.goal_type === 'quantitative' && (
            <div className="grid grid-cols-2 gap-4">
              <input
                className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-primary focus:outline-none"
                placeholder="Target value (e.g. 10000)"
                type="number"
                value={form.target_value}
                onChange={(e) => setForm({ ...form, target_value: e.target.value })}
              />
              <input
                className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-primary focus:outline-none"
                placeholder="Unit (e.g. steps, km, $)"
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value })}
              />
            </div>
          )}
          {form.goal_type === 'recurring' && (
            <select
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white focus:border-accent-primary focus:outline-none"
              value={form.recurrence}
              onChange={(e) => setForm({ ...form, recurrence: e.target.value })}
            >
              <option value="">Select frequency</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          )}
          <div className="flex gap-3">
            <input
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-primary focus:outline-none flex-1"
              placeholder="Due date (YYYY-MM-DD)"
              value={form.due_date}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })}
            />
            <input
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-primary focus:outline-none w-24"
              placeholder="XP"
              type="number"
              value={form.xp_reward}
              onChange={(e) => setForm({ ...form, xp_reward: Number(e.target.value) })}
            />
          </div>
          <div className="flex gap-3">
            <button
              onClick={createGoal}
              disabled={!form.title}
              className="px-6 py-2 bg-accent-primary text-black font-semibold rounded-lg hover:bg-accent-primary/80 transition disabled:opacity-30"
            >
              Create Goal
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-6 py-2 text-white/40 hover:text-white transition"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Goals List */}
      <div className="space-y-3">
        {goals.length === 0 && !showCreate && (
          <div className="text-center py-16 text-white/30">
            <div className="text-4xl mb-3">🎯</div>
            <p>No active goals yet. Create one to get started!</p>
          </div>
        )}
        {goals.map((g) => (
          <div key={g.id} className="bg-bg-card rounded-xl p-4 border border-white/5 card-glow">
            <div className="flex items-center gap-3">
              <span className="text-lg">{g.category_icon || '⭐'}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-white font-medium">{g.title}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-white/40">
                    {g.goal_type}
                  </span>
                  {g.recurrence && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-accent-primary/10 text-accent-primary">
                      {g.recurrence}
                    </span>
                  )}
                </div>
                {g.description && (
                  <p className="text-xs text-white/30 mt-1">{g.description}</p>
                )}
              </div>
              <span className="text-sm font-mono text-accent-xp">+{g.xp_reward}</span>
              {g.goal_type !== 'manual' && !g.sensor_attempted && (
                <button
                  onClick={() => proposeStrategies(g.id)}
                  className="px-3 py-1 text-xs bg-accent-primary/20 text-accent-primary rounded-lg hover:bg-accent-primary/30 transition"
                >
                  Set up tracking
                </button>
              )}
              <button
                onClick={() => completeGoal(g.id)}
                className="px-3 py-1 text-xs bg-accent-success/20 text-accent-success rounded-lg hover:bg-accent-success/30 transition"
              >
                Complete
              </button>
            </div>

            {/* Progress bar for quantitative goals */}
            {g.target_value && (
              <div className="mt-3">
                <div className="h-2 bg-bg-primary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent-primary rounded-full transition-all"
                    style={{ width: `${Math.min(((g.current_value || 0) / g.target_value) * 100, 100)}%` }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[10px] text-white/30">
                    {g.current_value || 0} / {g.target_value} {g.unit || ''}
                  </span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Tracking Strategy Selection Modal */}
      {strategyGoalId !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-bg-card rounded-xl border border-white/10 max-w-lg w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6">
              <h2 className="text-lg font-bold text-white mb-1">How should I track this?</h2>
              <p className="text-xs text-white/40 mb-5">Choose how you'd like progress to be monitored.</p>

              {loadingStrategies ? (
                <div className="text-center py-8 text-white/30">
                  <div className="text-2xl mb-2 animate-pulse">🤖</div>
                  <p className="text-sm">Analyzing tracking options...</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {strategies.map((s, i) => (
                    <button
                      key={s.id}
                      onClick={() => selectStrategy(i)}
                      disabled={selectingStrategy}
                      className="w-full text-left p-4 rounded-lg border border-white/5 hover:border-accent-primary/40 hover:bg-accent-primary/5 transition disabled:opacity-50"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-semibold text-white">{s.label}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                          s.automation_level === 'automatic' ? 'bg-accent-success/15 text-accent-success' :
                          s.automation_level === 'semi-automatic' ? 'bg-accent-primary/15 text-accent-primary' :
                          s.automation_level === 'user-assisted' ? 'bg-accent-xp/15 text-accent-xp' :
                          'bg-white/5 text-white/40'
                        }`}>
                          {s.automation_level}
                        </span>
                      </div>
                      <p className="text-xs text-white/50 mb-2">{s.approach}</p>
                      {s.setup_required && s.setup_required !== 'None' && (
                        <p className="text-[10px] text-accent-xp/70">Setup: {s.setup_required}</p>
                      )}
                    </button>
                  ))}
                </div>
              )}

              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => { setStrategyGoalId(null); setStrategies([]); }}
                  className="px-4 py-2 text-sm text-white/40 hover:text-white transition"
                >
                  Skip for now
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
