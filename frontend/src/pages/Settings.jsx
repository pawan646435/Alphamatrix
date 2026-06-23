import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Eye, Monitor, ShieldAlert, CheckCircle, Save, LogOut } from 'lucide-react';
import useAuth from '../hooks/useAuth';

export default function SettingsPage() {
  const { user, editProfile, logout } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved === 'false' ? 'light' : 'dark';
  });
  
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (user) {
      setDisplayName(user.displayName || user.email.split('@')[0]);
    } else {
      navigate('/login');
    }
  }, [user, navigate]);

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setSuccessMsg('');
    setErrorMsg('');
    try {
      await editProfile(displayName);
      setSuccessMsg('Operator profile information updated successfully.');
    } catch (err) {
      setErrorMsg(err.message || 'Failed to update profile settings.');
    } finally {
      setLoading(false);
    }
  };

  const handleThemeChange = (newTheme) => {
    setTheme(newTheme);
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
      localStorage.setItem('darkMode', 'true');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('darkMode', 'false');
    }
  };

  const handleLogoutClick = async () => {
    try {
      await logout();
      navigate('/login?logout=success');
    } catch (err) {
      console.error(err);
    }
  };

  if (!user) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-6 font-mono text-xs">
      {/* Title */}
      <div className="border-b border-brand-border/40 pb-4">
        <h1 className="text-sm font-bold uppercase tracking-widest font-display text-black dark:text-white">
          Operator Console Settings
        </h1>
        <p className="text-[10px] text-brand-textMuted uppercase tracking-wider mt-1">
          Configure security credentials, theme preferences, and platform rules
        </p>
      </div>

      {successMsg && (
        <div className="p-3 bg-brand-success/15 border border-brand-success/40 text-brand-success text-[10px] uppercase flex items-center gap-2">
          <CheckCircle className="h-4 w-4 shrink-0" />
          {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-brand-danger/15 border border-brand-danger/40 text-brand-danger text-[10px] uppercase flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          {errorMsg}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left column info panel */}
        <div className="md:col-span-1 space-y-4">
          <div className="bg-brand-surface border border-brand-border p-4 space-y-4">
            <div className="flex flex-col items-center text-center p-2">
              <div className="relative h-16 w-16 rounded-full border border-brand-primary bg-brand-bg flex items-center justify-center overflow-hidden mb-3">
                {user.photoURL ? (
                  <img src={user.photoURL} alt={displayName} className="h-full w-full object-cover" />
                ) : (
                  <User className="h-8 w-8 text-brand-primary" />
                )}
              </div>
              <h3 className="font-bold text-black dark:text-white truncate max-w-full">
                {displayName}
              </h3>
              <p className="text-[9px] text-brand-textMuted truncate max-w-full mt-0.5">
                {user.email}
              </p>
            </div>
            
            <div className="border-t border-brand-border/40 pt-3 space-y-2 text-[9px] uppercase tracking-wider">
              <div>
                <span className="text-brand-textMuted block">Session Status:</span>
                <span className="text-brand-success font-bold">🟢 Active / Secure</span>
              </div>
              <div>
                <span className="text-brand-textMuted block">Identity Provider:</span>
                <span className="text-brand-primary font-bold">
                  {user.providerData?.[0]?.providerId === 'google.com' ? 'Google Authenticated' : 'Secure Passcode'}
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={handleLogoutClick}
            className="w-full py-3 bg-brand-danger/10 border border-brand-danger/30 hover:border-brand-danger text-brand-danger text-[10px] uppercase font-bold tracking-wider transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <LogOut className="h-4 w-4" />
            Terminate Operator Session
          </button>
        </div>

        {/* Right column settings panels */}
        <div className="md:col-span-2 space-y-6">
          
          {/* PROFILE INFORMATION */}
          <section className="bg-brand-surface border border-brand-border p-5 space-y-4">
            <div className="border-b border-brand-border/40 pb-2">
              <h2 className="text-xs font-bold text-brand-primary uppercase tracking-wider">
                Profile Information
              </h2>
            </div>
            
            <form onSubmit={handleProfileUpdate} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-[9px] text-brand-textMuted uppercase font-bold">
                  Operator Display Name
                </label>
                <input
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full px-3 py-2 bg-brand-bg border border-brand-border text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary transition-all font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[9px] text-brand-textMuted uppercase font-bold">
                  Terminal Registered Email
                </label>
                <input
                  type="text"
                  disabled
                  value={user.email}
                  className="w-full px-3 py-2 bg-brand-bg/50 border border-brand-border/40 text-xs text-brand-textMuted font-mono cursor-not-allowed"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="py-2.5 px-4 bg-brand-primary text-black font-bold text-[10px] uppercase tracking-wider border border-brand-primary hover:bg-brand-primary/95 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <Save className="h-3.5 w-3.5" />
                {loading ? 'Saving...' : 'Apply Console Signature'}
              </button>
            </form>
          </section>

          {/* APPEARANCE */}
          <section className="bg-brand-surface border border-brand-border p-5 space-y-4">
            <div className="border-b border-brand-border/40 pb-2">
              <h2 className="text-xs font-bold text-brand-primary uppercase tracking-wider">
                Appearance Settings
              </h2>
            </div>

            <div className="space-y-2">
              <span className="block text-[9px] text-brand-textMuted uppercase font-bold">
                Console Theme Theme Preference
              </span>
              <div className="flex gap-4">
                <button
                  type="button"
                  onClick={() => handleThemeChange('dark')}
                  className={`flex-1 py-3 px-4 border transition-all text-center font-bold tracking-widest flex items-center justify-center gap-2 cursor-pointer ${
                    theme === 'dark'
                      ? 'border-brand-primary text-brand-primary bg-brand-primary/5'
                      : 'border-brand-border text-brand-textMuted hover:border-brand-primary/50'
                  }`}
                >
                  <Monitor className="h-4 w-4" />
                  Dark Theme
                </button>
                <button
                  type="button"
                  onClick={() => handleThemeChange('light')}
                  className={`flex-1 py-3 px-4 border transition-all text-center font-bold tracking-widest flex items-center justify-center gap-2 cursor-pointer ${
                    theme === 'light'
                      ? 'border-brand-primary text-brand-primary bg-brand-primary/5'
                      : 'border-brand-border text-brand-textMuted hover:border-brand-primary/50'
                  }`}
                >
                  <Eye className="h-4 w-4" />
                  Light Theme
                </button>
              </div>
            </div>
          </section>

          {/* FUTURE PLATFORM PREFERENCES */}
          <section className="bg-brand-surface border border-brand-border/40 p-5 space-y-4 opacity-75">
            <div className="border-b border-brand-border/20 pb-2">
              <h2 className="text-xs font-bold text-brand-textMuted uppercase tracking-wider">
                Platform Preferences & Subscription
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[9px] text-brand-textMuted uppercase tracking-widest">
              <div className="border border-brand-border/20 p-3 bg-brand-bg/25">
                <span className="block font-bold">Notification Prefs</span>
                <span className="text-[7px] text-brand-primary font-bold block mt-1">[Coming Soon]</span>
              </div>
              <div className="border border-brand-border/20 p-3 bg-brand-bg/25">
                <span className="block">Plan Type: Free Tier</span>
                <span className="text-[7px] text-brand-primary font-bold block mt-1">[Coming Soon]</span>
              </div>
              <div className="border border-brand-border/20 p-3 bg-brand-bg/25">
                <span className="block">Saved Research</span>
                <span className="text-[7px] text-brand-primary font-bold block mt-1">[Coming Soon]</span>
              </div>
              <div className="border border-brand-border/20 p-3 bg-brand-bg/25">
                <span className="block">Saved Comparisons</span>
                <span className="text-[7px] text-brand-primary font-bold block mt-1">[Coming Soon]</span>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
