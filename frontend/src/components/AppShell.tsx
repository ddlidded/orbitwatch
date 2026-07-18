import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';

export default function AppShell() {
  return (
    <div className='min-h-screen flex'>
      <Sidebar />
      <main className='flex-1 min-w-0 p-4 pb-6'>
        <Topbar />
        <Outlet />
      </main>
    </div>
  );
}
