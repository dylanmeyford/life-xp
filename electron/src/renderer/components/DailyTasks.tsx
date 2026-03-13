import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { DailyTask } from '../types';

export default function DailyTasks() {
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTasks = async () => {
    try {
      const data = await api.listDailyTasks();
      setTasks(data);
    } catch (err) {
      console.error('Failed to load tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTasks(); }, []);

  const completeTask = async (id: number) => {
    await api.completeDailyTask(id);
    loadTasks();
  };

  const skipTask = async (id: number) => {
    await api.skipDailyTask(id);
    loadTasks();
  };

  const done = tasks.filter(t => t.status === 'done').length;
  const total = tasks.length;

  if (loading) return <div className="text-white/30 text-sm">Loading tasks...</div>;

  return (
    <div className="bg-bg-card rounded-xl p-4 border border-white/5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">Today's Tasks</h3>
        <span className="text-xs font-mono text-accent-xp">{done}/{total}</span>
      </div>

      {tasks.length === 0 ? (
        <p className="text-white/30 text-sm">No tasks yet. Your AI coach will generate them each morning.</p>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <div
              key={task.id}
              className={`flex items-center gap-3 p-2 rounded-lg transition-all
                ${task.status === 'done' ? 'opacity-50' : 'hover:bg-white/5'}`}
            >
              <button
                onClick={() => task.status === 'pending' && completeTask(task.id)}
                className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all flex-shrink-0
                  ${task.status === 'done'
                    ? 'bg-accent-success/20 border-accent-success text-accent-success'
                    : task.status === 'skipped'
                    ? 'bg-white/5 border-white/20 text-white/20'
                    : 'border-white/20 hover:border-accent-primary'
                  }`}
                disabled={task.status !== 'pending'}
              >
                {task.status === 'done' && '✓'}
                {task.status === 'skipped' && '—'}
              </button>

              <div className="flex-1 min-w-0">
                <div className={`text-sm ${task.status === 'done' ? 'line-through text-white/40' : 'text-white'}`}>
                  {task.title}
                </div>
                {task.goal_title && (
                  <div className="text-xs text-white/30">{task.goal_title}</div>
                )}
              </div>

              <span className="text-xs font-mono text-accent-xp flex-shrink-0">
                +{task.xp_reward}
              </span>

              {task.status === 'pending' && (
                <button
                  onClick={() => skipTask(task.id)}
                  className="text-xs text-white/20 hover:text-white/50"
                  title="Skip"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
