import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Goals from './pages/Goals';
import Habits from './pages/Habits';
import Quests from './pages/Quests';
import Rewards from './pages/Rewards';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/habits" element={<Habits />} />
        <Route path="/quests" element={<Quests />} />
        <Route path="/rewards" element={<Rewards />} />
      </Routes>
    </Layout>
  );
}
