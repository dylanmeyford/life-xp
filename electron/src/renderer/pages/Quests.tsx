import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Quest } from '../types';

export default function Quests() {
  const [quests, setQuests] = useState<Quest[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: '', description: '', category: 'Productivity', xp_reward: 500, deadline: '',
    objectives: [''],
  });

  const loadQuests = () => api.listQuests().then(setQuests);
  useEffect(() => { loadQuests(); }, []);

  const addObjective = () => setForm({ ...form, objectives: [...form.objectives, ''] });
  const updateObjective = (i: number, val: string) => {
    const objs = [...form.objectives];
    objs[i] = val;
    setForm({ ...form, objectives: objs });
  };

  const createQuest = async () => {
    await api.createQuest({
      ...form,
      xp_reward: Number(form.xp_reward),
      deadline: form.deadline || null,
      objectives: form.objectives.filter(o => o.trim()),
    });
    setShowCreate(false);
    setForm({ title: '', description: '', category: 'Productivity', xp_reward: 500, deadline: '', objectives: [''] });
    loadQuests();
  };

  const completeObjective = async (questId: number, objId: number) => {
    await api.completeObjective(questId, objId);
    loadQuests();
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">🏆 Quests</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-accent-level/20 text-accent-level rounded-lg hover:bg-accent-level/30 transition text-sm font-medium"
        >
          + New Quest
        </button>
      </div>

      {showCreate && (
        <div className="bg-bg-card rounded-xl p-6 border border-white/5 mb-6 space-y-4">
          <input
            className="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-level focus:outline-none"
            placeholder="Quest title (e.g. Healthy Week)"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div className="space-y-2">
            <label className="text-xs text-white/40">Objectives:</label>
            {form.objectives.map((obj, i) => (
              <input
                key={i}
                className="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-level focus:outline-none"
                placeholder={`Objective ${i + 1}`}
                value={obj}
                onChange={(e) => updateObjective(i, e.target.value)}
              />
            ))}
            <button onClick={addObjective} className="text-xs text-accent-level hover:text-accent-level/80">
              + Add objective
            </button>
          </div>
          <div className="flex gap-3">
            <button onClick={createQuest} disabled={!form.title} className="px-6 py-2 bg-accent-level text-black font-semibold rounded-lg hover:bg-accent-level/80 transition disabled:opacity-30">
              Create Quest
            </button>
            <button onClick={() => setShowCreate(false)} className="px-6 py-2 text-white/40 hover:text-white transition">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {quests.length === 0 && !showCreate && (
          <div className="text-center py-16 text-white/30">
            <div className="text-4xl mb-3">🏆</div>
            <p>No active quests. Create a multi-objective challenge!</p>
          </div>
        )}
        {quests.map((q) => {
          const done = q.objectives.filter(o => o.completed).length;
          const total = q.objectives.length;
          return (
            <div key={q.id} className="bg-bg-card rounded-xl p-5 border border-white/5 card-glow">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-bold text-white">{q.title}</h3>
                <span className="text-sm font-mono text-accent-xp">+{q.xp_reward} XP</span>
              </div>

              <div className="h-2 bg-bg-primary rounded-full overflow-hidden mb-4">
                <div
                  className="h-full bg-accent-level rounded-full transition-all"
                  style={{ width: `${q.progress * 100}%` }}
                />
              </div>

              <div className="space-y-2">
                {q.objectives.map((obj) => (
                  <div key={obj.id} className="flex items-center gap-3">
                    <button
                      onClick={() => !obj.completed && completeObjective(q.id, obj.id)}
                      className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all flex-shrink-0
                        ${obj.completed
                          ? 'bg-accent-success/20 border-accent-success text-accent-success'
                          : 'border-white/20 hover:border-accent-level'
                        }`}
                      disabled={!!obj.completed}
                    >
                      {obj.completed ? '✓' : ''}
                    </button>
                    <span className={`text-sm ${obj.completed ? 'line-through text-white/30' : 'text-white'}`}>
                      {obj.description}
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-3 text-xs text-white/30">{done}/{total} completed</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
