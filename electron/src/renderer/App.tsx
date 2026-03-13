import { Routes, Route, Outlet } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Goals from './pages/Goals';
import Habits from './pages/Habits';
import Quests from './pages/Quests';
import Rewards from './pages/Rewards';
import TrayDashboard from './pages/TrayDashboard';

function MainLayout() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Tray popover — no sidebar, compact view */}
      <Route path="/tray" element={<TrayDashboard />} />

      {/* Main app — full layout with sidebar */}
      <Route element={<MainLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/habits" element={<Habits />} />
        <Route path="/quests" element={<Quests />} />
        <Route path="/rewards" element={<Rewards />} />
      </Route>
    </Routes>
  );
}
