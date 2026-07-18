import { useEffect, useState } from 'react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { User } from '../types';

interface Role {
  id: string;
  name: string;
  description?: string;
}

export default function UserManagement() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [editing, setEditing] = useState<User | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [resetUser, setResetUser] = useState<User | null>(null);

  const fetchUsers = async () => {
    try {
      const res = await api.get('/admin/users');
      setUsers(res.data.items || []);
      const r = await api.get('/admin/roles');
      setRoles(r.data || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleDelete = async (id: string) => {
    if (id === currentUser?.id) return;
    if (!confirm('Delete this user?')) return;
    try {
      await api.delete(`/admin/users/${id}`);
      setMessage('User deleted.');
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Delete failed');
    }
  };

  const handleToggleActive = async (u: User) => {
    if (u.id === currentUser?.id) return;
    try {
      await api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active });
      setMessage(`User ${u.is_active ? 'disabled' : 'enabled'}.`);
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Update failed');
    }
  };

  if (loading) return <div className='p-10 text-orbit-muted'>Loading users...</div>;

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <div className='flex items-center justify-between mb-3'>
          <h2 className='text-[13px] font-semibold'>User Management</h2>
          <button
            onClick={() => { setShowCreate(true); setEditing(null); setError(''); }}
            className='h-[28px] px-2.5 rounded-md bg-orbit-blue text-white text-[11px]'
          >
            + Add User
          </button>
        </div>

        {(error || message) && (
          <div className={`mb-3 p-2 rounded text-[10px] ${error ? 'bg-red-950 text-red-200' : 'bg-orbit-deep text-orbit-text'}`}>
            {error || message}
          </div>
        )}

        <div className='overflow-x-auto'>
          <table className='w-full text-[11px]'>
            <thead>
              <tr className='text-left text-orbit-muted border-b border-orbit-border/30'>
                <th className='pb-2 font-medium'>Name</th>
                <th className='pb-2 font-medium'>Email</th>
                <th className='pb-2 font-medium'>Roles</th>
                <th className='pb-2 font-medium'>Status</th>
                <th className='pb-2 font-medium text-right'>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className='border-b border-orbit-border/20 last:border-0'>
                  <td className='py-2 text-orbit-text'>{u.full_name}</td>
                  <td className='py-2 text-orbit-muted'>{u.email}</td>
                  <td className='py-2 text-orbit-muted'>{u.roles.join(', ') || '—'}</td>
                  <td className='py-2'>
                    <span className={`px-1.5 py-0.5 rounded-full text-[9px] ${u.is_active ? 'bg-green-950 text-green-200' : 'bg-red-950 text-red-200'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className='py-2 text-right space-x-1'>
                    <button onClick={() => { setEditing(u); setShowCreate(false); setError(''); }} className='text-[10px] text-orbit-blue hover:underline'>Edit</button>
                    <button onClick={() => { setResetUser(u); }} className='text-[10px] text-orbit-blue hover:underline'>Reset Password</button>
                    <button
                      onClick={() => handleToggleActive(u)}
                      disabled={u.id === currentUser?.id}
                      className={`text-[10px] ${u.id === currentUser?.id ? 'text-orbit-muted' : 'text-orbit-text hover:underline'}`}
                    >
                      {u.is_active ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      onClick={() => handleDelete(u.id)}
                      disabled={u.id === currentUser?.id}
                      className={`text-[10px] ${u.id === currentUser?.id ? 'text-orbit-muted' : 'text-red-400 hover:underline'}`}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {(showCreate || editing) && (
        <UserForm
          user={editing}
          roles={roles}
          onCancel={() => { setShowCreate(false); setEditing(null); }}
          onSaved={() => { setShowCreate(false); setEditing(null); setMessage('User saved.'); fetchUsers(); }}
          onError={(e) => setError(e)}
        />
      )}

      {resetUser && (
        <ResetPasswordForm
          user={resetUser}
          onCancel={() => setResetUser(null)}
          onSaved={() => { setResetUser(null); setMessage('Password reset.'); fetchUsers(); }}
          onError={(e) => setError(e)}
        />
      )}
    </div>
  );
}

function UserForm({
  user,
  roles,
  onCancel,
  onSaved,
  onError,
}: {
  user: User | null;
  roles: Role[];
  onCancel: () => void;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [form, setForm] = useState({
    email: user?.email || '',
    full_name: user?.full_name || '',
    password: '',
    role_names: user?.roles || [],
  });
  const [submitting, setSubmitting] = useState(false);

  const toggleRole = (name: string) => {
    setForm((f) => ({
      ...f,
      role_names: f.role_names.includes(name)
        ? f.role_names.filter((r) => r !== name)
        : [...f.role_names, name],
    }));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (user) {
        const payload: Record<string, any> = {
          full_name: form.full_name,
          role_names: form.role_names,
        };
        await api.patch(`/admin/users/${user.id}`, payload);
      } else {
        if (!form.password || form.password.length < 12) {
          onError('Password must be at least 12 characters');
          setSubmitting(false);
          return;
        }
        await api.post('/admin/users', {
          email: form.email,
          full_name: form.full_name,
          password: form.password,
          role_names: form.role_names,
        });
      }
      onSaved();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Save failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className='p-3.5 rounded-lg border border-orbit-border bg-orbit-panel shadow-orbit'>
      <h3 className='text-[12px] font-semibold mb-3'>{user ? 'Edit User' : 'Add User'}</h3>
      <form onSubmit={submit} className='grid grid-cols-1 md:grid-cols-2 gap-3'>
        <div>
          <label className='block text-[10px] text-orbit-muted mb-1'>Full Name</label>
          <input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder='e.g. Jane Analyst'
            className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            required
          />
        </div>
        <div>
          <label className='block text-[10px] text-orbit-muted mb-1'>Email</label>
          <input
            type='email'
            value={form.email}
            disabled={!!user}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder='jane@isotopiq.dev'
            className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none disabled:opacity-50'
            required
          />
        </div>
        {!user && (
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Initial Password</label>
            <input
              type='password'
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder='Minimum 12 characters'
              minLength={12}
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
              required={!user}
            />
          </div>
        )}
        <div className='md:col-span-2'>
          <label className='block text-[10px] text-orbit-muted mb-1'>Roles</label>
          <div className='flex flex-wrap gap-2'>
            {roles.map((role) => (
              <label key={role.id} className='flex items-center gap-1.5 text-[11px] text-orbit-text cursor-pointer'>
                <input
                  type='checkbox'
                  checked={form.role_names.includes(role.name)}
                  onChange={() => toggleRole(role.name)}
                  className='rounded border-orbit-border bg-orbit-soft'
                />
                <span className='capitalize'>{role.name.replace('_', ' ')}</span>
              </label>
            ))}
          </div>
        </div>
        <div className='md:col-span-2 flex gap-2'>
          <button type='submit' disabled={submitting} className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px]'>
            {submitting ? 'Saving...' : 'Save'}
          </button>
          <button type='button' onClick={onCancel} className='h-[32px] px-3 rounded-md border border-orbit-border text-orbit-text text-[11px] hover:bg-orbit-soft'>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function ResetPasswordForm({
  user,
  onCancel,
  onSaved,
  onError,
}: {
  user: User;
  onCancel: () => void;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 12) {
      onError('Password must be at least 12 characters');
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/admin/users/${user.id}/reset-password`, { new_password: password });
      onSaved();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Reset failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className='p-3.5 rounded-lg border border-orbit-border bg-orbit-panel shadow-orbit'>
      <h3 className='text-[12px] font-semibold mb-3'>Reset password for {user.full_name}</h3>
      <form onSubmit={submit} className='flex gap-2'>
        <input
          type='password'
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder='New password (min 12 chars)'
          minLength={12}
          className='flex-1 h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
          required
        />
        <button type='submit' disabled={submitting} className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px]'>
          Reset
        </button>
        <button type='button' onClick={onCancel} className='h-[32px] px-3 rounded-md border border-orbit-border text-orbit-text text-[11px] hover:bg-orbit-soft'>
          Cancel
        </button>
      </form>
    </div>
  );
}
