import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await login(email, password, rememberMe);
      navigate('/dashboard');
    } catch (err: any) {
      const data = err.response?.data;
      const message =
        data?.error?.message ||
        (Array.isArray(data?.detail)
          ? data.detail.map((d: any) => d.msg).join('; ')
          : data?.detail) ||
        'Login failed';
      setError(message);
    }
  };

  return (
    <div className='min-h-screen flex items-center justify-center bg-orbit-bg'>
      <div className='w-full max-w-md p-8 rounded-xl border border-orbit-border bg-orbit-panel shadow-orbit'>
        <div className='flex justify-center mb-6'>
          <img src='/logo.png' alt='isotopiq' className='h-10 object-contain' />
        </div>
        {error && <div className='mb-4 p-3 rounded bg-orbit-red/10 text-orbit-red text-sm'>{error}</div>}
        <form onSubmit={submit} className='space-y-4'>
          <div>
            <label className='block text-xs text-orbit-muted mb-1'>Email</label>
            <input
              type='email'
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder='admin@isotopiq.dev'
              className='w-full h-10 rounded-md border border-orbit-border bg-orbit-soft px-3 text-sm outline-none'
              required
            />
          </div>
          <div>
            <label className='block text-xs text-orbit-muted mb-1'>Password</label>
            <input
              type='password'
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder='Enter your password'
              className='w-full h-10 rounded-md border border-orbit-border bg-orbit-soft px-3 text-sm outline-none'
              required
            />
          </div>
          <label className='flex items-center gap-2 text-xs text-orbit-text cursor-pointer'>
            <input
              type='checkbox'
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className='rounded border-orbit-border bg-orbit-soft'
            />
            Remember me
          </label>
          <button className='w-full h-10 rounded-md bg-orbit-blue text-white font-medium text-sm'>
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
