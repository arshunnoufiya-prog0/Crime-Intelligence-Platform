import { useState } from 'react';
import '../styles/intel.css';

/**
 * Real login against POST /api/accounts/login/ (change-1 plumbing, recorded
 * in artifacts/frontend_inventory.md): the SSE consumer needs a Bearer
 * token, so the fake client-side login is replaced by the actual backend
 * flow. The role shown after login comes from the SERVER, not this form —
 * the legacy dropdown no longer decides anything.
 */
export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password || busy) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch('/api/accounts/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const body = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setError(body?.error || `login failed (${resp.status})`);
        return;
      }
      if (body?.access) {
        localStorage.setItem('access_token', body.access);
      }
      if (body?.refresh) {
        localStorage.setItem('refresh_token', body.refresh);
      }
      onLoginSuccess(body?.user || { name: email, role: 'INVESTIGATOR' });
    } catch (err) {
      setError(err.message || 'network error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-blue-600 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">🔍 KSP Intelligence</h1>
          <p className="text-sm text-gray-600 mt-2">Crime Investigation Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="officer@crime.local"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
              required
            />
          </div>

          {error && (
            <div className="text-sm text-red-700 bg-red-100 border border-red-300 rounded px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-2 rounded-lg transition"
          >
            {busy ? 'Signing in…' : '🔓 Login'}
          </button>
        </form>

        <p className="text-center text-xs text-gray-600 mt-6">
          Accounts are provisioned by the administrator (§17 RBAC).
        </p>
      </div>
    </div>
  );
}
