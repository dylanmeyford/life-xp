import { NavLink } from 'react-router-dom';
import { ReactNode } from 'react';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '⚔️' },
  { path: '/goals', label: 'Goals', icon: '🎯' },
  { path: '/habits', label: 'Habits', icon: '🔥' },
  { path: '/quests', label: 'Quests', icon: '🏆' },
  { path: '/rewards', label: 'Rewards', icon: '🎁' },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <nav className="w-16 bg-bg-secondary flex flex-col items-center py-4 gap-2 border-r border-white/5">
        {/* Titlebar drag area */}
        <div className="titlebar h-6 w-full" />

        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `w-11 h-11 flex items-center justify-center rounded-xl text-lg transition-all
              ${isActive
                ? 'bg-accent-primary/20 shadow-lg shadow-accent-primary/10'
                : 'hover:bg-white/5'
              }`
            }
            title={item.label}
          >
            {item.icon}
          </NavLink>
        ))}
      </nav>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-6">
        {/* Titlebar drag area */}
        <div className="titlebar h-4 -mt-6 -mx-6 mb-2" />
        {children}
      </main>
    </div>
  );
}
