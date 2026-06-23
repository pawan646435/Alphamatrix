import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldCheck, Mail, Lock, RefreshCw } from 'lucide-react';
import useAuth from '../hooks/useAuth';

export default function Login() {
  const navigate = useNavigate();
  const { loginWithEmail, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('logout') === 'success' ? 'Successfully terminated session.' : '';
  });

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const user = await loginWithEmail(email, password);
      const token = await user.getIdToken();
      localStorage.setItem('alphamatrix_token', token);
      localStorage.setItem('alphamatrix_user_email', user.email);
      navigate('/stocks');
    } catch (err) {
      if (err.code === 'auth/wrong-password' || err.code === 'auth/user-not-found' || err.code === 'auth/invalid-credential') {
        setError('Access authorization denied. Invalid credentials.');
      } else if (err.code === 'auth/network-request-failed') {
        setError('Network uplink failure. Check connection settings.');
      } else {
        setError(err.message || 'Login failed. Please verify credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const user = await loginWithGoogle();
      const token = await user.getIdToken();
      localStorage.setItem('alphamatrix_token', token);
      localStorage.setItem('alphamatrix_user_email', user.email);
      navigate('/stocks');
    } catch (err) {
      if (err.code === 'auth/popup-blocked') {
        setError('Terminal identity popup was blocked by browser.');
      } else {
        setError(err.message || 'Google authentication failed.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-brand-surface border border-brand-border p-6 sm:p-8 shadow-2xl relative">
        <div className="absolute top-2 left-2 text-brand-textMuted font-mono text-[8px]">+ [SECURE_LOGIN_GATE]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted font-mono text-[8px]">[FORCED_SSL] +</div>

        <div className="text-center space-y-2 pt-4">
          <div className="mx-auto h-12 w-12 border border-brand-primary/30 rounded-lg flex items-center justify-center bg-brand-primary/5">
            <ShieldCheck className="h-6 w-6 text-brand-primary" />
          </div>
          <h2 className="text-sm font-bold uppercase tracking-widest font-display text-black dark:text-white">
            ALPHAMATRIX TERMINAL AUTH
          </h2>
          <p className="text-[10px] text-brand-textMuted font-mono uppercase tracking-wide">
            Access secure quantitative intelligence & AI research
          </p>
        </div>

        {success && (
          <div className="p-3 bg-brand-success/10 border border-brand-success/30 text-brand-success font-mono text-[10px] uppercase text-center">
            {success}
          </div>
        )}

        {error && (
          <div className="p-3 bg-brand-danger/10 border border-brand-danger/30 text-brand-danger font-mono text-[10px] uppercase text-center">
            {error}
          </div>
        )}

        <form className="mt-8 space-y-4" onSubmit={handleEmailLogin}>
          <div className="space-y-3 font-mono text-xs">
            {/* Email Field */}
            <div className="space-y-1">
              <label className="block text-[9px] font-bold text-brand-primary uppercase tracking-wider">
                EMAIL ADDRESS
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-brand-textMuted" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full pl-9 pr-3 py-3 min-h-[44px] bg-brand-bg border border-brand-border text-xs text-black dark:text-white placeholder-brand-textMuted focus:outline-none focus:border-brand-primary transition-all font-mono"
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-1">
              <label className="block text-[9px] font-bold text-brand-primary uppercase tracking-wider">
                ACCESS PASSCODE
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-brand-textMuted" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-3 min-h-[44px] bg-brand-bg border border-brand-border text-xs text-black dark:text-white placeholder-brand-textMuted focus:outline-none focus:border-brand-primary transition-all font-mono"
                />
              </div>
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 min-h-[48px] px-4 bg-brand-primary text-black font-bold font-mono text-xs uppercase tracking-widest border border-brand-primary hover:bg-brand-primary/90 hover:shadow-[0_0_15px_rgba(201,165,107,0.3)] transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              {loading ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                'SECURE SIGN IN'
              )}
            </button>
          </div>
        </form>

        <div className="relative flex py-2 items-center">
          <div className="flex-grow border-t border-brand-border/40"></div>
          <span className="flex-shrink mx-4 text-brand-textMuted font-mono text-[9px] uppercase">OR CONNECT VIA</span>
          <div className="flex-grow border-t border-brand-border/40"></div>
        </div>

        <div>
          <button
            onClick={handleGoogleLogin}
            disabled={loading}
            className="w-full py-3.5 min-h-[48px] px-4 border border-brand-border hover:border-brand-primary text-black dark:text-white font-bold font-mono text-xs uppercase tracking-widest bg-brand-bg hover:shadow-[0_0_15px_rgba(201,165,107,0.15)] transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <svg className="h-4 w-4 text-brand-primary" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12.24 10.285V13.4h6.887C18.2 15.614 15.645 18 12.24 18c-3.86 0-7-3.14-7-7s3.14-7 7-7c1.7 0 3.3.6 4.5 1.8l2.4-2.4C17.3 1.8 14.9 1 12.24 1c-5.5 0-10 4.5-10 10s4.5 10 10 10c5.7 0 9.5-4 9.5-9.66 0-.6-.05-1.2-.15-1.74l-9.35-.01z"/>
            </svg>
            GOOGLE IDENTITY GATE
          </button>
        </div>

        <div className="text-center font-mono text-[10px] uppercase text-brand-textMuted pt-2">
          New system operator?{' '}
          <Link to="/signup" className="text-brand-primary hover:underline font-bold">
            REQUEST SYSTEM ACCESS (SIGN UP)
          </Link>
        </div>
      </div>
    </div>
  );
}
