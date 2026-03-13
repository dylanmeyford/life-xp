export interface Stats {
  total_xp: number;
  level: number;
  xp_in_level: number;
  xp_for_next: number;
  progress_pct: number;
  title: string;
}

export interface Goal {
  id: number;
  title: string;
  description: string | null;
  category_id: number | null;
  category_name: string | null;
  category_icon: string | null;
  category_color: string | null;
  parent_id: number | null;
  xp_reward: number;
  status: string;
  goal_type: string;
  recurrence: string | null;
  llm_context: string | null;
  sensor_attempted: number;
  target_value: number | null;
  current_value: number | null;
  unit: string | null;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Habit {
  id: number;
  title: string;
  description: string | null;
  category_name: string | null;
  category_icon: string | null;
  category_color: string | null;
  frequency: string;
  xp_per_check: number;
  streak: number;
  done_today: boolean;
}

export interface Quest {
  id: number;
  title: string;
  description: string | null;
  category_name: string | null;
  category_icon: string | null;
  xp_reward: number;
  status: string;
  deadline: string | null;
  objectives: QuestObjective[];
  progress: number;
}

export interface QuestObjective {
  id: number;
  quest_id: number;
  description: string;
  completed: number;
  sort_order: number;
}

export interface Reward {
  id: number;
  title: string;
  description: string | null;
  xp_cost: number;
}

export interface DailyTask {
  id: number;
  goal_id: number | null;
  title: string;
  description: string | null;
  date: string;
  status: string;
  xp_reward: number;
  generated_by: string;
  goal_title: string | null;
}

export interface AppNotification {
  id: number;
  title: string;
  message: string;
  notification_type: string;
  action_type: string | null;
  action_data: string | null;
  read: number;
  created_at: string;
}

export interface HabitGridData {
  habit_id: number;
  weeks: number;
  checked_dates: string[];
}

export interface XPHistoryEntry {
  day: string;
  xp: number;
}

export interface TrackingStrategy {
  id: number;
  label: string;
  approach: string;
  data_source: string;
  setup_required: string;
  confidence: number;
  automation_level: 'automatic' | 'semi-automatic' | 'user-assisted' | 'manual';
}
