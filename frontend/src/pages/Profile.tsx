import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { User } from '../types';

export default function Profile() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<Partial<User>>({});
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user && !loading) {
      navigate('/login');
      return;
    }
    setProfile({
      full_name: user?.full_name || '',
      email: user?.email || '',
    });
    setLoading(false);
  }, [user, navigate, loading]);

  const updateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    setError('');
    try {
      const payload: Record<string, string> = {};
      if (profile.full_name) payload.full_name = profile.full_name;
      if (profile.email) payload.email = profile.email;
      await api.patch('/auth/me', payload);
      await refresh();
      setMessage('Profile updated.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update profile');
    }
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    setError('');
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setMessage('Password changed. Please log in again.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => navigate('/login'), 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to change password');
    }
  };

  if (loading) return <div className='p-10 text-orbit-muted'>Loading profile...</div>;

  return (
    <div className='space-y-2.5'>
      <div className='p-3.5 rounded-lg border border-orbit-border bg-gradient-to-b from-orbit-panel to-orbit-soft shadow-orbit'>
        <h2 className='text-[13px] font-semibold mb-3'>User Profile</h2>
        {(message || error) && (
          <div className={`mb-3 p-2 rounded text-[10px] ${error ? 'bg-red-950 text-red-200' : 'bg-orbit-deep text-orbit-text'}`}>
            {error || message}
          </div>
        )}
        <form onSubmit={updateProfile} className='grid grid-cols-1 md:grid-cols-2 gap-3 mb-6'>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Full Name</label>
            <input
              value={profile.full_name || ''}
              onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
              placeholder='Full name'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Email</label>
            <input
              type='email'
              value={profile.email || ''}
              onChange={(e) => setProfile({ ...profile, email: e.target.value })}
              placeholder='email@isotopiq.dev'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div className='md:col-span-2'>
            <button type='submit' className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px]'>
              Update Profile
            </button>
          </div>
        </form>

        <h3 className='text-[12px] font-semibold mb-2'>Change Password</h3>
        <form onSubmit={changePassword} className='grid grid-cols-1 md:grid-cols-2 gap-3'>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Current Password</label>
            <input
              type='password'
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder='Current password'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div />
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>New Password</label>
            <input
              type='password'
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder='New password (min 12 chars)'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div>
            <label className='block text-[10px] text-orbit-muted mb-1'>Confirm New Password</label>
            <input
              type='password'
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder='Confirm new password'
              className='w-full h-[32px] px-2 rounded-md border border-orbit-border bg-orbit-soft text-orbit-text text-[11px] outline-none'
            />
          </div>
          <div className='md:col-span-2'>
            <button type='submit' className='h-[32px] px-3 rounded-md bg-orbit-blue text-white text-[11px]'>
              Change Password
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
