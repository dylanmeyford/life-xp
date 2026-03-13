import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Reward, Stats } from '../types';

export default function Rewards() {
  const [rewards, setRewards] = useState<Reward[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', xp_cost: 500 });

  const load = () => {
    api.listRewards().then(setRewards);
    api.getStats().then(setStats);
  };
  useEffect(() => { load(); }, []);

  const createReward = async () => {
    await api.createReward(form);
    setShowCreate(false);
    setForm({ title: '', description: '', xp_cost: 500 });
    load();
  };

  const redeemReward = async (id: number) => {
    try {
      await api.redeemReward(id);
      load();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">🎁 Rewards</h1>
        <div className="flex items-center gap-4">
          {stats && (
            <span className="text-sm font-mono text-accent-xp">
              Balance: {stats.total_xp.toLocaleString()} XP
            </span>
          )}
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-4 py-2 bg-accent-xp/20 text-accent-xp rounded-lg hover:bg-accent-xp/30 transition text-sm font-medium"
          >
            + Add Reward
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="bg-bg-card rounded-xl p-6 border border-white/5 mb-6 space-y-4">
          <input
            className="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30 focus:border-accent-xp focus:outline-none"
            placeholder="Reward name (e.g. Nice dinner out)"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-4">
            <input
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white placeholder-white/30"
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <input
              className="bg-bg-primary border border-white/10 rounded-lg px-4 py-2 text-white"
              type="number"
              placeholder="XP Cost"
              value={form.xp_cost}
              onChange={(e) => setForm({ ...form, xp_cost: Number(e.target.value) })}
            />
          </div>
          <div className="flex gap-3">
            <button onClick={createReward} disabled={!form.title} className="px-6 py-2 bg-accent-xp text-black font-semibold rounded-lg hover:bg-accent-xp/80 transition disabled:opacity-30">
              Add Reward
            </button>
            <button onClick={() => setShowCreate(false)} className="px-6 py-2 text-white/40 hover:text-white transition">Cancel</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {rewards.length === 0 && !showCreate && (
          <div className="col-span-2 text-center py-16 text-white/30">
            <div className="text-4xl mb-3">🎁</div>
            <p>No rewards yet. Add treats you can earn with XP!</p>
          </div>
        )}
        {rewards.map((r) => {
          const affordable = stats && stats.total_xp >= r.xp_cost;
          return (
            <div key={r.id} className="bg-bg-card rounded-xl p-5 border border-white/5 card-glow">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-white font-semibold">{r.title}</h3>
                  {r.description && (
                    <p className="text-xs text-white/30 mt-1">{r.description}</p>
                  )}
                </div>
                <span className="text-lg font-mono text-accent-xp font-bold">{r.xp_cost}</span>
              </div>
              <button
                onClick={() => redeemReward(r.id)}
                disabled={!affordable}
                className={`mt-4 w-full py-2 rounded-lg font-medium text-sm transition
                  ${affordable
                    ? 'bg-accent-xp/20 text-accent-xp hover:bg-accent-xp/30'
                    : 'bg-white/5 text-white/20 cursor-not-allowed'
                  }`}
              >
                {affordable ? 'Redeem' : `Need ${(r.xp_cost - (stats?.total_xp || 0)).toLocaleString()} more XP`}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
