import { Bell, ChevronDown, LogOut, Menu, User } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ThemeToggle from './ThemeToggle';

export default function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const initials = user?.full_name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() || 'U';

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleLogout = async () => {
    setOpen(false);
    await logout();
    navigate('/login');
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
        <button className='w-9 h-9 rounded-full border border-orbit-border bg-orbit-soft text-orbit-text flex items-center justify-center hover:bg-orbit-hover relative'>
          <Bell size={18} />
          <span className='absolute right-0 top-0 w-3.5 h-3.5 rounded-full bg-[#d83b3b] text-white text-[9px] font-bold grid place-items-center border-2 border-orbit-bg'>
            3
          </span>
        </button>
        <ThemeToggle />
        <div ref={ref} className='relative'>
          <button
            onClick={() => setOpen((v) => !v)}
            className='flex items-center gap-2 outline-none'
          >
            <div className='w-9 h-9 rounded-full grid place-items-center bg-[#152236] text-[#edf4ff] text-xs font-extrabold border border-[#203149]'>
              {initials}
            </div>
            <ChevronDown size={14} className={`text-orbit-muted transition-transform ${open ? 'rotate-180' : ''}`} />
          </button>
          {open && (
            <div className='absolute right-0 top-full mt-2 w-56 rounded-lg border border-orbit-border bg-orbit-panel shadow-orbit z-50 py-2'>
              <div className='px-3 py-2 border-b border-orbit-border/30'>
                <div className='text-[12px] font-semibold text-orbit-text'>{user?.full_name}</div>
                <div className='text-[10px] text-orbit-muted truncate'>{user?.email}</div>
                <div className='text-[9px] text-[#65a8ff] mt-0.5 capitalize'>{user?.roles?.join(', ') || 'User'}</div>
              </div>
              <button
                onClick={() => { setOpen(false); navigate('/settings'); }}
                className='w-full flex items-center gap-2 px-3 py-2 text-[11px] text-orbit-text hover:bg-orbit-soft'
              >
                <User size={14} /> Settings
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
