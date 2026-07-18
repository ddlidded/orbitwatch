import { useEffect, useState } from 'react';
import api from '../api/client';
import ThemeToggle from '../components/ThemeToggle';
import type { User } from '../types';

export default function Settings() {
  const [users, setUsers] = useState<User[]>([]);
  const [newUser, setNewUser] = useState({ email: '', full_name: '', password: '', role_names: 'operator' });
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get('/admin/users?limit=100').then((res) => setUsers(res.data.items || []));
  }, []);

  const createUser = async () => {
    try {
      await api.post('/admin/users', { ...newUser, role_names: [newUser.role_names] });
      setMessage('User created.');
      setNewUser({ email: '', full_name: '', password: '', role_names: 'operator' });
      api.get('/admin/users?limit=100').then((res) => setUsers(res.data.items || []));
    } catch (err: any) {
      setMessage(err.response?.data?.error?.message || 'Failed to create user');
    }
  };

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold mb-3'>Settings</h2>
        <div className='flex items-center gap-3 text-[11px] text-orbit-muted'>
          <span>Theme</span>
          <ThemeToggle />
        </div>
      </div>

      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h3 className='text-[12px] font-semibold mb-2'>Users</h3>
        {message && <div className='mb-3 p-2 rounded text-[10px] bg-orbit-deep text-orbit-text'>{message}</div>}
        <div className='grid grid-cols-1 md:grid-cols-4 gap-2 mb-3'>
          <input
            value={newUser.email}
            onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
            placeholder='Email'
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          />
          <input
            value={newUser.full_name}
            onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
            placeholder='Full name'
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          />
          <input
            type='password'
            value={newUser.password}
            onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
            placeholder='Password'
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          />
          <select
            value={newUser.role_names}
            onChange={(e) => setNewUser({ ...newUser, role_names: e.target.value })}
            className='h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          >
            <option value='operator'>Operator</option>
            <option value='lab_manager'>Lab Manager</option>
            <option value='system_admin'>System Admin</option>
          </select>
          <button
            onClick={createUser}
            disabled={!newUser.email || !newUser.password || !newUser.full_name}
            className='md:col-span-4 h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px] disabled:opacity-50'
          >
            Create User
          </button>
        </div>
        <table className='w-full border-collapse min-w-[500px] text-[10px]'>
          <thead>
            <tr className='text-left text-orbit-muted'>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Email</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Name</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Roles</th>
              <th className='p-2 bg-orbit-soft border-y border-orbit-border font-semibold'>Active</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className='border-b border-orbit-border/5 hover:bg-orbit-hover'>
                <td className='p-2'>{u.email}</td>
                <td className='p-2'>{u.full_name}</td>
                <td className='p-2'>{u.roles.join(', ')}</td>
                <td className='p-2'>{u.is_active ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
