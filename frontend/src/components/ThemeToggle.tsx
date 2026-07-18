import { Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));

  useEffect(() => {
    const saved = localStorage.getItem('orbitwatch-theme');
    if (saved === 'dark') {
      document.documentElement.classList.add('dark');
      setDark(true);
    } else if (saved === 'light') {
      document.documentElement.classList.remove('dark');
      setDark(false);
    }
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    if (next) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('orbitwatch-theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('orbitwatch-theme', 'light');
    }
  };

  return (
    <button
      onClick={toggle}
      className='w-9 h-9 rounded-full border border-orbit-border bg-orbit-soft text-orbit-text flex items-center justify-center hover:bg-orbit-hover'
      aria-label='Toggle theme'
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
