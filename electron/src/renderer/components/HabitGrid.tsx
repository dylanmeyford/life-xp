import { useEffect, useState } from 'react';
import { api } from '../api/client';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DAYS = ['Mon','','Wed','','Fri','','Sun'];

export default function HabitGrid({ habitId, title, weeks = 52 }: {
  habitId: number;
  title: string;
  weeks?: number;
}) {
  const [checkedDates, setCheckedDates] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.getHabitGrid(habitId, weeks).then((data) => {
      setCheckedDates(new Set(data.checked_dates));
    });
  }, [habitId, weeks]);

  // Build grid
  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - (weeks * 7 - 1));
  // Align to Monday
  const dayOfWeek = startDate.getDay();
  const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  startDate.setDate(startDate.getDate() + mondayOffset);

  const grid: (string | null)[][] = [];
  const currentDate = new Date(startDate);

  while (currentDate <= today) {
    const week: (string | null)[] = [];
    for (let d = 0; d < 7; d++) {
      if (currentDate > today) {
        week.push(null);
      } else {
        const iso = currentDate.toISOString().slice(0, 10);
        week.push(checkedDates.has(iso) ? iso : '');
      }
      currentDate.setDate(currentDate.getDate() + 1);
    }
    grid.push(week);
  }

  const totalChecks = checkedDates.size;

  return (
    <div className="bg-bg-card rounded-xl p-4 border border-white/5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <span className="text-xs text-white/40">{totalChecks} checks</span>
      </div>

      <div className="flex gap-[2px]">
        {/* Day labels */}
        <div className="flex flex-col gap-[2px] mr-1">
          {DAYS.map((day, i) => (
            <div key={i} className="h-[12px] text-[9px] text-white/30 leading-[12px] w-6">
              {day}
            </div>
          ))}
        </div>

        {/* Grid columns (weeks) */}
        {grid.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-[2px]">
            {week.map((cell, di) => {
              let cellClass = 'grid-cell grid-cell-0';
              if (cell === null) {
                cellClass = 'grid-cell opacity-0';
              } else if (cell) {
                cellClass = 'grid-cell grid-cell-4';
              }
              return (
                <div
                  key={di}
                  className={cellClass}
                  title={cell || undefined}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
