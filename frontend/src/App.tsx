import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import AppShell from './components/AppShell';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import TicOverview from './pages/TicOverview';
import SampleDetail from './pages/SampleDetail';
import PeakMonitor from './pages/PeakMonitor';
import SystemHealth from './pages/SystemHealth';
import SequenceQueue from './pages/SequenceQueue';
import TargetLists from './pages/TargetLists';
import EventsAlerts from './pages/EventsAlerts';
import Reports from './pages/Reports';
import ExportData from './pages/ExportData';
import Settings from './pages/Settings';
import Profile from './pages/Profile';
import NotFound from './pages/NotFound';

function ProtectedRoute({ children, roles }: { children: React.ReactNode; roles?: string[] }) {
  const { user, loading } = useAuth();
  if (loading) return <div className='p-10 text-orbit-muted'>Initializing OrbitWatch...</div>;
  if (!user) return <Navigate to='/login' replace />;
  if (roles && !roles.some((r) => user.roles.includes(r))) {
    return <Navigate to='/unauthorized' replace />;
  }
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path='/login' element={<Login />} />
      <Route path='/' element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
        <Route index element={<Dashboard />} />
        <Route path='dashboard' element={<Dashboard />} />
        <Route path='tic' element={<TicOverview />} />
        <Route path='samples/:sampleId' element={<SampleDetail />} />
        <Route path='peaks' element={<PeakMonitor />} />
        <Route path='health' element={<SystemHealth />} />
        <Route path='sequence' element={<SequenceQueue />} />
        <Route path='targets' element={<TargetLists />} />
        <Route path='events' element={<EventsAlerts />} />
        <Route path='reports' element={<Reports />} />
        <Route path='export' element={<ExportData />} />
        <Route path='settings' element={<Settings />} />
        <Route path='profile' element={<Profile />} />
        <Route path='unauthorized' element={<div className='p-10'>Unauthorized</div>} />
      </Route>
      <Route path='*' element={<NotFound />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
