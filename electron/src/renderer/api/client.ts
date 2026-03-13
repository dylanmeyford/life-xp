const API_BASE = 'http://localhost:8111';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  // Stats
  getStats: () => request<any>('/api/stats'),

  // Goals
  listGoals: (status = 'active') => request<any[]>(`/api/goals?status=${status}`),
  createGoal: (data: any) => request<any>('/api/goals', { method: 'POST', body: JSON.stringify(data) }),
  completeGoal: (id: number) => request<any>(`/api/goals/${id}/complete`, { method: 'PUT' }),
  updateProgress: (id: number, value: number) =>
    request<any>(`/api/goals/${id}/progress`, { method: 'PUT', body: JSON.stringify({ value }) }),

  // Habits
  listHabits: () => request<any[]>('/api/habits'),
  createHabit: (data: any) => request<any>('/api/habits', { method: 'POST', body: JSON.stringify(data) }),
  checkHabit: (id: number) => request<any>(`/api/habits/${id}/check`, { method: 'PUT' }),
  getHabitGrid: (id: number, weeks = 52) => request<any>(`/api/habits/${id}/grid?weeks=${weeks}`),
  getHabitOverview: (weeks = 20) => request<any>(`/api/habits/overview?weeks=${weeks}`),

  // Quests
  listQuests: (status = 'active') => request<any[]>(`/api/quests?status=${status}`),
  createQuest: (data: any) => request<any>('/api/quests', { method: 'POST', body: JSON.stringify(data) }),
  completeObjective: (questId: number, objId: number) =>
    request<any>(`/api/quests/${questId}/objectives/${objId}/complete`, { method: 'PUT' }),

  // Rewards
  listRewards: () => request<any[]>('/api/rewards'),
  createReward: (data: any) => request<any>('/api/rewards', { method: 'POST', body: JSON.stringify(data) }),
  redeemReward: (id: number) => request<any>(`/api/rewards/${id}/redeem`, { method: 'PUT' }),

  // Daily Tasks
  listDailyTasks: (date?: string) => request<any[]>(`/api/daily-tasks${date ? `?task_date=${date}` : ''}`),
  createDailyTask: (data: any) => request<any>('/api/daily-tasks', { method: 'POST', body: JSON.stringify(data) }),
  completeDailyTask: (id: number) => request<any>(`/api/daily-tasks/${id}/complete`, { method: 'PUT' }),
  skipDailyTask: (id: number) => request<any>(`/api/daily-tasks/${id}/skip`, { method: 'PUT' }),

  // Coach
  decomposeGoal: (goalId: number) =>
    request<any>('/api/coach/decompose', { method: 'POST', body: JSON.stringify({ goal_id: goalId }) }),
  getDailyPlan: () => request<any>('/api/coach/daily-plan', { method: 'POST' }),
  evaluateProgress: (goalId: number, message: string) =>
    request<any>('/api/coach/evaluate', { method: 'POST', body: JSON.stringify({ goal_id: goalId, message }) }),

  // Notifications
  getPendingNotifications: () => request<any[]>('/api/notifications/pending'),

  // Categories & History
  listCategories: () => request<any[]>('/api/categories'),
  getXPHistory: (days = 30) => request<any[]>(`/api/xp/history?days=${days}`),

  // Sensors
  listSensors: () => request<any>('/api/sensors'),
  proposeTracking: (goalId: number) =>
    request<any>('/api/sensors/propose', { method: 'POST', body: JSON.stringify({ goal_id: goalId }) }),
  getStrategies: (goalId: number) => request<any>(`/api/sensors/strategies/${goalId}`),
  selectStrategy: (goalId: number, strategyIndex: number) =>
    request<any>('/api/sensors/select', { method: 'POST', body: JSON.stringify({ goal_id: goalId, strategy_index: strategyIndex }) }),

  // Health
  health: () => request<any>('/api/health'),
};
