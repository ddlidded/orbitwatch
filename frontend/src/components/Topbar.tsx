import { Bell, ChevronDown, Menu } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ThemeToggle from './ThemeToggle';

export default function Topbar() {
  const { user } = useAuth();
  const initials = user?.full_name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() || 'U';

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
        <div className='w-9 h-9 rounded-full grid place-items-center bg-[#152236] text-[#edf4ff] text-xs font-extrabold border border-[#203149]'>
          {initials}
        </div>
        <ChevronDown size={14} className='text-orbit-muted' />
      </div>
    </header>
  );
}
