import { Activity, BarChart3, Clock, Cpu, Home, Shield, Users, type LucideIcon } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { Instrument } from '../types';

const icons: Record<string, LucideIcon> = {
  home: Home,
  'bar-chart': BarChart3,
  user: Users,
  activity: Activity,
  clock: Clock,
  shield: Shield,
  cpu: Cpu,
};

interface SidebarProps {
  instrument?: Instrument;
}

export default function Sidebar({ instrument }: SidebarProps) {
  const { user } = useAuth();
  const isAdmin = user?.roles.includes('system_admin');
  const isInstrumentManager = isAdmin || user?.roles.includes('instrument_admin');
  const nav = [
    { label: 'Dashboard', path: '/dashboard', icon: 'home' },
    { label: 'TIC Overview', path: '/tic', icon: 'bar-chart' },
    { label: 'Sample Detail', path: '/samples/current', icon: 'user', badge: true },
    { label: 'Peak Monitor', path: '/peaks', icon: 'activity' },
    { label: 'System Health', path: '/health', icon: 'clock' },
  ];

  return (
    <aside className='w-[232px] flex-shrink-0 min-h-screen bg-orbit-sidebar border-r border-orbit-border flex flex-col p-4 pb-5 sticky top-0 h-screen overflow-y-auto'>
      <div className='flex items-center px-2 pb-5'>
        <img src='/logo.png' alt='isotopiq' className='w-[164px] h-auto object-contain' />
      </div>

      <nav className='flex-1'>
        <div className='mt-3'>
          <div className='text-[10px] text-orbit-muted uppercase tracking-wider px-3 mb-2'>Live monitoring</div>
          {nav.map((item) => {
            const Icon = icons[item.icon] || Home;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 mb-[3px] rounded-md text-[13px] transition-colors ${
                    isActive
                      ? 'text-white bg-gradient-to-br from-[#2f73dc] to-[#2457c8] shadow-[0_10px_22px_rgba(37,99,235,0.22)]'
                      : 'text-orbit-muted hover:bg-orbit-soft hover:text-orbit-text'
                  }`
                }
              >
                <Icon size={17} />
                <span>{item.label}</span>
                {item.badge && <span className='ml-auto w-1.5 h-1.5 rounded-full bg-[#438dff]' />}
              </NavLink>
            );
          })}
        </div>

        <div className='mt-6'>
          <div className='text-[10px] text-orbit-muted uppercase tracking-wider px-3 mb-2'>Management</div>
          <NavLink to='/sequence' className='nav-item-sub'>Sequence Queue</NavLink>
          <NavLink to='/targets' className='nav-item-sub'>Target Lists</NavLink>
          <NavLink to='/events' className='nav-item-sub'>Events &amp; Alerts</NavLink>
          <NavLink to='/reports' className='nav-item-sub'>Reports</NavLink>
          <NavLink to='/export' className='nav-item-sub'>Export Data</NavLink>
          <NavLink to='/settings' className='nav-item-sub'>Settings</NavLink>
          {isAdmin && <NavLink to='/admin/users' className='nav-item-sub'>User Management</NavLink>}
          {isInstrumentManager && <NavLink to='/connect-instrument' className='nav-item-sub'>Connect Instrument</NavLink>}
        </div>
      </nav>

      <div className='mt-auto border border-orbit-border bg-orbit-panel rounded-lg p-3.5 shadow-orbit'>
        <div className='flex items-center gap-2 text-xs font-bold'>
          Instrument Status
          <span className='w-2 h-2 rounded-full bg-orbit-green shadow-[0_0_0_4px_rgba(62,207,102,0.1)]' />
        </div>
        <div className='text-[11px] text-orbit-green mt-2.5'>{instrument?.status || 'Acquiring'}</div>
        <div className='text-[10px] text-orbit-muted mt-2.5 leading-relaxed'>
          {instrument?.name || 'Exploris 480'}<br />
          Serial: {instrument?.serial_number || 'IQLAAEGAAPFADBMK'}<br />
          Tune 3.4.0.3122<br />
          IAPI 3.8.0.57
        </div>
      </div>

      <div className='text-[10px] text-orbit-faint mt-4 mx-2 leading-relaxed'>
        OrbitWatch v1.0.0<br />© 2024 isotopiq
      </div>
    </aside>
  );
}
