import { Bell, ChevronDown, LogOut, Menu, User } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import useWebSocket from '../hooks/useWebSocket';
import ThemeToggle from './ThemeToggle';
import type { AlertItem, Instrument } from '../types';

export default function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const profileRef = useRef<HTMLDivElement>(null);
  const bellRef = useRef<HTMLDivElement>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [notifications, setNotifications] = useState<AlertItem[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);

  const initials = user?.full_name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() || 'U';

  const fetchNotifications = useCallback(() => {
    api.get('/alerts/notifications').then((res) => {
      setNotifications(res.data.items || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    fetchNotifications();
    api.get('/instruments').then((res) => setInstruments(res.data || [])).catch(() => {});
    const interval = setInterval(fetchNotifications, 10000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  const onAlertMessage = useCallback((msg: any) => {
    if (msg?.payload?.type === 'alert.created') {
      fetchNotifications();
    }
  }, [fetchNotifications]);

  const alertChannels = instruments.map((i) => `alerts:${i.id}`);
  useWebSocket(onAlertMessage, alertChannels);

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileOpen(false);
      }
      if (bellRef.current && !bellRef.current.contains(event.target as Node)) {
        setBellOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleLogout = async () => {
    setProfileOpen(false);
    await logout();
    navigate('/login');
  };

  const acknowledge = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.post(`/alerts/notifications/${id}/acknowledge`, { notes: 'Acknowledged from notification dropdown' });
      fetchNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  const openEvents = () => {
    setBellOpen(false);
    navigate('/events');
  };

  return (
    <header className='flex items-center justify-between mb-3.5 px-1'>
      <div className='flex items-center gap-2.5'>
        <button className='lg:hidden w-9 h-9 grid place-items-center rounded-full border border-orbit-border bg-orbit-soft'>
          <Menu size={18} />
        </button>
        <h1 className='text-[21px] font-semibold tracking-tight'>OrbitWatch</h1>
        <span className='hidden sm:inline-flex text-[10px] text-[#c5d2e4] bg-[#111e30] border border-[#203044] px-2 py-1 rounded-full'>
          Exploris 480
        </span>
      </div>
      <div className='flex items-center gap-3'>
        <div ref={bellRef} className='relative'>
          <button
            onClick={() => setBellOpen((v) => !v)}
            className='w-9 h-9 rounded-full border border-orbit-border bg-orbit-soft text-orbit-text flex items-center justify-center hover:bg-orbit-hover relative'
          >
            <Bell size={18} />
            {notifications.length > 0 && (
              <span className='absolute right-0 top-0 w-3.5 h-3.5 rounded-full bg-[#d83b3b] text-white text-[9px] font-bold grid place-items-center border-2 border-orbit-bg'>
                {notifications.length > 9 ? '9+' : notifications.length}
              </span>
            )}
          </button>
          {bellOpen && (
            <div className='absolute right-0 top-full mt-2 w-80 rounded-lg border border-orbit-border bg-orbit-panel shadow-orbit z-50 py-2'>
              <div className='px-3 py-2 border-b border-orbit-border/30 flex items-center justify-between'>
                <div className='text-[12px] font-semibold text-orbit-text'>Notifications</div>
                <button onClick={openEvents} className='text-[10px] text-orbit-blue hover:underline'>View all</button>
              </div>
              <div className='max-h-64 overflow-auto'>
                {notifications.length === 0 ? (
                  <div className='px-3 py-4 text-[11px] text-orbit-muted'>No open alerts.</div>
                ) : (
                  notifications.map((n) => (
                    <div key={n.id} className='px-3 py-2 border-b border-orbit-border/10 hover:bg-orbit-soft cursor-pointer' onClick={openEvents}>
                      <div className='flex items-center justify-between gap-2 mb-0.5'>
                        <span className={`text-[10px] font-semibold ${n.severity === 'critical' || n.severity === 'error' ? 'text-red-400' : n.severity === 'warning' ? 'text-yellow-400' : 'text-orbit-text'}`}>
                          {n.category}
                        </span>
                        <span className='text-[9px] text-orbit-muted'>{new Date(n.last_seen_at).toLocaleTimeString()}</span>
                      </div>
                      <div className='text-[11px] text-orbit-text truncate'>{n.message}</div>
                      {n.status === 'open' && (
                        <button
                          onClick={(e) => acknowledge(n.id, e)}
                          className='mt-1.5 text-[10px] text-orbit-blue hover:underline'
                        >
                          Mark as read
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
        <ThemeToggle />
        <div ref={profileRef} className='relative'>
          <button
            onClick={() => setProfileOpen((v) => !v)}
            className='flex items-center gap-2 outline-none'
          >
            <div className='w-9 h-9 rounded-full grid place-items-center bg-[#152236] text-[#edf4ff] text-xs font-extrabold border border-[#203149]'>
              {initials}
            </div>
            <ChevronDown size={14} className={`text-orbit-muted transition-transform ${profileOpen ? 'rotate-180' : ''}`} />
          </button>
          {profileOpen && (
            <div className='absolute right-0 top-full mt-2 w-56 rounded-lg border border-orbit-border bg-orbit-panel shadow-orbit z-50 py-2'>
              <div className='px-3 py-2 border-b border-orbit-border/30'>
                <div className='text-[12px] font-semibold text-orbit-text'>{user?.full_name}</div>
                <div className='text-[10px] text-orbit-muted truncate'>{user?.email}</div>
                <div className='text-[9px] text-[#65a8ff] mt-0.5 capitalize'>{user?.roles?.join(', ') || 'User'}</div>
              </div>
              <button
                onClick={() => { setProfileOpen(false); navigate('/profile'); }}
                className='w-full flex items-center gap-2 px-3 py-2 text-[11px] text-orbit-text hover:bg-orbit-soft'
              >
                <User size={14} /> Profile
              </button>
              <button
                onClick={handleLogout}
                className='w-full flex items-center gap-2 px-3 py-2 text-[11px] text-[#ff6d61] hover:bg-orbit-soft'
              >
                <LogOut size={14} /> Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
