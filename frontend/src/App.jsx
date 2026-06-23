import React, { useState, useEffect, Suspense, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate, Navigate } from 'react-router-dom';
import { LayoutDashboard, Compass, Sun, Moon, Star, RefreshCw, GitCompare, Newspaper, Menu, X, LogOut, LogIn, ChevronDown, User, Settings } from 'lucide-react';
import AlphaMatrixLogo from './components/AlphaMatrixLogo';
import Home from './pages/Home';
import Explorer from './pages/Explorer';
import Detail from './pages/Detail';
import Login from './pages/Login';
import Signup from './pages/Signup';
import SettingsPage from './pages/Settings';
import { AuthProvider } from './context/AuthContext';
import useAuth from './hooks/useAuth';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="h-[60vh] flex flex-col items-center justify-center text-brand-textMuted font-mono">
        <RefreshCw className="h-6 w-6 animate-spin text-brand-primary mb-3" />
        <p className="text-[10px] tracking-wider">VERIFYING ACCESS GATE...</p>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

// Lazy loaded Stock Pages
const StockHome = React.lazy(() => import('./pages/StockHome'));
const StockExplorer = React.lazy(() => import('./pages/StockExplorer'));
const StockDetail = React.lazy(() => import('./pages/StockDetail'));
const StockSector = React.lazy(() => import('./pages/StockSector'));
const StockWatchlist = React.lazy(() => import('./pages/StockWatchlist'));
const StockCompare = React.lazy(() => import('./pages/StockCompare'));
const News = React.lazy(() => import('./pages/News'));

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, loading, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const [exploreDropdownOpen, setExploreDropdownOpen] = useState(false);
  
  const dropdownRef = useRef(null);
  const exploreRef = useRef(null);

  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved ? saved === 'true' : true;
  });

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setProfileDropdownOpen(false);
      }
      if (exploreRef.current && !exploreRef.current.contains(event.target)) {
        setExploreDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setTimeout(() => setMobileMenuOpen(false), 0);
  }, [location.pathname]);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [mobileMenuOpen]);

  const handleLogout = async () => {
    await logout();
    setProfileDropdownOpen(false);
    navigate('/login?logout=success');
  };

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('darkMode', String(isDark));
  }, [isDark]);

  const activeSegment = location.pathname.startsWith('/stocks') ? 'stocks' : 'funds';
  const dashboardLink = activeSegment === 'stocks' ? '/stocks' : '/';
  const explorerLink = activeSegment === 'stocks' ? '/stocks/explorer' : '/explorer';

  const isActive = (path) => location.pathname === path;
  const isDashboardActive = location.pathname === '/' || location.pathname === '/funds' || location.pathname === '/stocks';

  // Shared nav link class builder
  const navLinkClass = (active) =>
    `flex items-center gap-2 px-3 py-2 transition-all font-mono text-[10px] uppercase tracking-wider border ${
      active
        ? 'text-brand-primary border-brand-primary bg-brand-primary/5'
        : 'text-brand-textMuted border-transparent hover:text-brand-primary hover:border-brand-primary'
    }`;

  // Mobile drawer link class — larger touch targets
  const drawerLinkClass = (active) =>
    `flex items-center gap-3 px-4 py-4 w-full font-mono text-[11px] uppercase tracking-widest border-b border-brand-border/40 transition-all ${
      active
        ? 'text-brand-primary bg-brand-primary/10'
        : 'text-brand-textMuted hover:text-brand-primary hover:bg-brand-primary/5'
    }`;

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-brand-bg text-brand-textMuted font-mono">
        <RefreshCw className="h-8 w-8 animate-spin text-brand-primary mb-4" />
        <p className="text-[12px] tracking-widest uppercase">BOOTING ALPHAMATRIX PLATFORM GATEWAY...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col selection:bg-brand-primary selection:text-brand-bg bg-brand-bg text-black dark:text-white transition-colors duration-300">

      {/* ── MOBILE DRAWER OVERLAY ── */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm sm:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── MOBILE DRAWER PANEL ── */}
      <aside
        className={`fixed top-0 left-0 h-full w-[280px] z-[70] bg-brand-bg border-r border-brand-border flex flex-col transition-transform duration-300 ease-in-out sm:hidden ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Mobile navigation"
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-brand-border">
          <Link to={dashboardLink} className="flex items-center gap-2 group">
            <AlphaMatrixLogo size={32} showGlow={false} />
            <span className="text-sm font-extrabold tracking-wider text-black dark:text-white font-display uppercase">
              ALPHAMATRIX
            </span>
          </Link>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="p-2 text-brand-textMuted hover:text-brand-primary transition-colors"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Segment Toggle inside drawer */}
        <div className="flex m-4 bg-brand-surface border border-brand-border p-0.5 rounded-lg font-mono text-[9px] uppercase tracking-wider">
          <Link
            to="/funds"
            className={`flex-1 text-center px-3 py-2 rounded-md transition-all ${
              activeSegment === 'funds'
                ? 'bg-brand-primary text-black font-extrabold shadow-sm'
                : 'text-brand-textMuted'
            }`}
          >
            Mutual Funds
          </Link>
          <Link
            to="/stocks"
            className={`flex-1 text-center px-3 py-2 rounded-md transition-all ${
              activeSegment === 'stocks'
                ? 'bg-brand-primary text-black font-extrabold shadow-sm'
                : 'text-brand-textMuted'
            }`}
          >
            Stocks
          </Link>
        </div>

        {/* Drawer Nav Links */}
        <nav className="flex flex-col flex-1 overflow-y-auto">
          <Link to={dashboardLink} className={drawerLinkClass(isDashboardActive)}>
            <LayoutDashboard className="h-4 w-4 text-brand-primary" />
            Dashboard
          </Link>
          <Link to="/news" className={drawerLinkClass(isActive('/news'))}>
            <Newspaper className="h-4 w-4 text-brand-primary" />
            News
            <span className="ml-auto w-2 h-2 rounded-full bg-brand-success animate-pulse" />
          </Link>
          <Link to={explorerLink} className={drawerLinkClass(location.pathname.endsWith('/explorer'))}>
            <Compass className="h-4 w-4 text-brand-primary" />
            Matrix Explorer
          </Link>
          {activeSegment === 'stocks' && (
            <Link to="/stocks/compare" className={drawerLinkClass(isActive('/stocks/compare'))}>
              <GitCompare className="h-4 w-4 text-brand-primary" />
              Compare Mode
            </Link>
          )}
          {user && (
            <>
              <Link to="/stocks/watchlist" className={drawerLinkClass(isActive('/stocks/watchlist'))}>
                <Star className="h-4 w-4 text-brand-primary" />
                AI Watchlist
              </Link>
              <Link to="/settings" className={drawerLinkClass(isActive('/settings'))}>
                <Settings className="h-4 w-4 text-brand-primary" />
                Console Settings
              </Link>
            </>
          )}
        </nav>

        {/* Drawer Footer: theme + auth */}
        <div className="border-t border-brand-border p-4 flex flex-col gap-3">
          <button
            onClick={() => setIsDark(!isDark)}
            className="flex items-center gap-3 w-full px-3 py-3 font-mono text-[10px] uppercase tracking-widest text-brand-textMuted hover:text-brand-primary border border-brand-border hover:border-brand-primary transition-all"
          >
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {isDark ? 'Light Mode' : 'Dark Mode'}
          </button>

          {user ? (
            <div className="flex flex-col gap-2">
              <span className="text-[9px] font-mono text-brand-primary uppercase px-1 truncate">
                [{user.displayName || user.email.split('@')[0]}]
              </span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 w-full px-3 py-3 font-mono text-[10px] uppercase tracking-widest text-brand-danger border border-brand-danger/30 hover:border-brand-danger transition-all cursor-pointer"
              >
                <LogOut className="h-4 w-4" />
                Terminate Session
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-2 w-full px-3 py-3 font-mono text-[10px] uppercase tracking-widest text-brand-primary border border-brand-primary hover:bg-brand-primary/10 transition-all"
            >
              <LogIn className="h-4 w-4" />
              Login
            </Link>
          )}
        </div>
      </aside>

      {/* ── MAIN HEADER ── */}
      <header className="sticky top-0 z-50 px-4 sm:px-6 py-3 sm:py-4 flex justify-between items-center bg-brand-bg/95 backdrop-blur-md border-b border-brand-border shadow-md">

        {/* Left: Hamburger (mobile) + Logo + Segment toggle (desktop) */}
        <div className="flex items-center gap-3">

          {/* Hamburger — mobile only */}
          <button
            id="mobile-menu-btn"
            onClick={() => setMobileMenuOpen(true)}
            className="sm:hidden p-2 text-brand-textMuted hover:text-brand-primary border border-brand-border hover:border-brand-primary transition-all rounded-md"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <Link to={dashboardLink} className="flex items-center gap-2.5 group">
            <AlphaMatrixLogo size={36} showGlow={true} className="group-hover:shadow-[0_0_15px_rgba(201,165,107,0.25)] transition-all duration-300 rounded-lg" />
            <span className="text-lg font-extrabold tracking-wider text-black dark:text-white font-display uppercase group-hover:text-brand-primary transition-colors">
              ALPHAMATRIX
            </span>
          </Link>

          {/* Segment selector — desktop only */}
          <div className="hidden sm:flex bg-brand-surface border border-brand-border p-0.5 rounded-lg font-mono text-[9px] uppercase tracking-wider">
            <Link
              to="/funds"
              className={`px-3 py-1 rounded-md transition-all ${
                activeSegment === 'funds'
                  ? 'bg-brand-primary text-black font-extrabold shadow-sm'
                  : 'text-brand-textMuted hover:text-black dark:hover:text-white'
              }`}
            >
              Mutual Funds
            </Link>
            <Link
              to="/stocks"
              className={`px-3 py-1 rounded-md transition-all ${
                activeSegment === 'stocks'
                  ? 'bg-brand-primary text-black font-extrabold shadow-sm'
                  : 'text-brand-textMuted hover:text-black dark:hover:text-white'
              }`}
            >
              Stocks
            </Link>
          </div>
        </div>

        {/* Right: Desktop nav (hidden on mobile) */}
        <nav className="hidden sm:flex items-center gap-3 font-mono text-[10px] uppercase tracking-wider">
          <Link to={dashboardLink} className={navLinkClass(isDashboardActive)}>
            <LayoutDashboard className="h-3.5 w-3.5 text-brand-primary" />
            [Dashboard]
          </Link>
          <Link to="/news" className={navLinkClass(isActive('/news'))}>
            <Newspaper className="h-3.5 w-3.5 text-brand-primary" />
            [News]
            <span className="w-1 h-1 rounded-full bg-brand-success animate-pulse" />
          </Link>

          {/* Explore Dropdown */}
          <div className="relative" ref={exploreRef}>
            <button
              onClick={() => setExploreDropdownOpen(!exploreDropdownOpen)}
              className="flex items-center gap-1.5 px-3 py-2 transition-all font-mono text-[10px] uppercase tracking-wider text-brand-textMuted hover:text-brand-primary border border-transparent hover:border-brand-primary cursor-pointer select-none focus:outline-none"
            >
              <Compass className="h-3.5 w-3.5 text-brand-primary" />
              Explore
              <ChevronDown className={`h-3 w-3 transition-transform duration-200 ${exploreDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {exploreDropdownOpen && (
              <div className="absolute left-0 mt-2 w-52 bg-brand-surface border border-brand-border shadow-2xl p-2 z-[100] font-mono text-[10px] animate-in fade-in slide-in-from-top-1 duration-150">
                <Link
                  to={explorerLink}
                  onClick={() => setExploreDropdownOpen(false)}
                  className="flex items-center gap-2.5 w-full px-3 py-2 text-left text-brand-textMuted hover:text-brand-primary hover:bg-brand-primary/5 transition-all uppercase"
                >
                  <Compass className="h-3.5 w-3.5" />
                  Matrix Explorer
                </Link>

                {activeSegment === 'stocks' && (
                  <Link
                    to="/stocks/compare"
                    onClick={() => setExploreDropdownOpen(false)}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-left text-brand-textMuted hover:text-brand-primary hover:bg-brand-primary/5 transition-all uppercase"
                  >
                    <GitCompare className="h-3.5 w-3.5" />
                    Compare Mode
                  </Link>
                )}

                {user && (
                  <Link
                    to="/stocks/watchlist"
                    onClick={() => setExploreDropdownOpen(false)}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-left text-brand-textMuted hover:text-brand-primary hover:bg-brand-primary/5 transition-all uppercase"
                  >
                    <Star className="h-3.5 w-3.5" />
                    AI Watchlist
                  </Link>
                )}

                <div className="flex items-center justify-between w-full px-3 py-2 text-left text-brand-textMuted/40 cursor-not-allowed uppercase select-none border-t border-brand-border/40 mt-1 pt-2">
                  <div className="flex items-center gap-2">
                    <span className="h-3.5 w-3.5 flex items-center justify-center text-[10px] font-bold font-mono">PT</span>
                    Portfolio Tracker
                  </div>
                  <span className="text-[7px] text-brand-primary font-bold">[Soon]</span>
                </div>

                <div className="flex items-center justify-between w-full px-3 py-2 text-left text-brand-textMuted/40 cursor-not-allowed uppercase select-none">
                  <div className="flex items-center gap-2">
                    <span className="h-3.5 w-3.5 flex items-center justify-center text-[10px] font-bold font-mono">SR</span>
                    Saved Research
                  </div>
                  <span className="text-[7px] text-brand-primary font-bold">[Soon]</span>
                </div>
              </div>
            )}
          </div>

          {isDark ? (
            <button
              onClick={() => setIsDark(false)}
              className="p-1.5 border border-brand-border hover:border-brand-primary hover:text-brand-primary transition-all flex items-center justify-center text-brand-textMuted"
              aria-label="Light Mode"
            >
              <Sun className="h-3.5 w-3.5" />
            </button>
          ) : (
            <button
              onClick={() => setIsDark(true)}
              className="p-1.5 border border-brand-border hover:border-brand-primary hover:text-brand-primary transition-all flex items-center justify-center text-brand-textMuted"
              aria-label="Dark Mode"
            >
              <Moon className="h-3.5 w-3.5" />
            </button>
          )}
          {user ? (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                className="relative flex items-center justify-center h-8 w-8 rounded-full border border-brand-border hover:border-brand-primary transition-all bg-brand-surface cursor-pointer select-none focus:outline-none"
              >
                {user.photoURL ? (
                  <img
                    src={user.photoURL}
                    alt={user.displayName || 'Operator'}
                    className="h-full w-full rounded-full object-cover"
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.style.display = 'none';
                    }}
                  />
                ) : null}
                {!user.photoURL && (
                  <span className="text-[10px] font-bold font-mono text-brand-primary">
                    {(() => {
                      const name = user.displayName || user.email.split('@')[0];
                      const parts = name.split(/[\s._-]+/);
                      if (parts.length >= 2) {
                        return (parts[0][0] + parts[1][0]).toUpperCase();
                      }
                      return name.substring(0, 2).toUpperCase();
                    })()}
                  </span>
                )}
                {/* Online indicator green dot */}
                <span className="absolute bottom-0 right-0 block h-2 w-2 rounded-full bg-brand-success ring-1 ring-brand-bg" />
              </button>

              {profileDropdownOpen && (
                <div className="absolute right-0 mt-2.5 w-60 bg-brand-surface border border-brand-border shadow-2xl p-2.5 z-[100] font-mono text-[10px] animate-in fade-in slide-in-from-top-1 duration-150">
                  <div className="px-3 py-2.5 border-b border-brand-border/40 mb-2 text-left">
                    <div className="text-brand-primary font-bold tracking-wider text-[8px] uppercase">OPERATOR CONSOLE</div>
                    <div className="text-black dark:text-white font-extrabold truncate mt-0.5 text-xs">
                      {user.displayName || 'UNNAMED OPERATOR'}
                    </div>
                    <div className="text-brand-textMuted truncate text-[9px] lowercase mt-0.5">
                      {user.email}
                    </div>
                    <div className="text-[8px] text-brand-textMuted/80 mt-1 uppercase tracking-wider">
                      Connected via: <span className="text-brand-primary font-bold">{user.providerData?.[0]?.providerId === 'google.com' ? 'Google Identity' : 'Secure Passcode'}</span>
                    </div>
                  </div>
                  
                  <Link
                    to={dashboardLink}
                    onClick={() => setProfileDropdownOpen(false)}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-left text-brand-textMuted hover:text-brand-primary hover:bg-brand-primary/5 transition-all uppercase"
                  >
                    <LayoutDashboard className="h-3.5 w-3.5" />
                    Dashboard
                  </Link>

                  <Link
                    to="/stocks/watchlist"
                    onClick={() => setProfileDropdownOpen(false)}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-left text-brand-textMuted hover:text-brand-primary hover:bg-brand-primary/5 transition-all uppercase"
                  >
                    <Star className="h-3.5 w-3.5" />
                    AI Watchlist
                  </Link>

                  <div className="flex items-center justify-between w-full px-3 py-2 text-left text-brand-textMuted/40 cursor-not-allowed uppercase select-none">
                    <div className="flex items-center gap-2.5">
                      <span className="h-3.5 w-3.5 flex items-center justify-center text-[10px] font-bold font-mono">SR</span>
                      Saved Research
                    </div>
                    <span className="text-[7px] text-brand-primary font-bold">[Soon]</span>
                  </div>

                  <div className="flex items-center justify-between w-full px-3 py-2 text-left text-brand-textMuted/40 cursor-not-allowed uppercase select-none">
                    <div className="flex items-center gap-2.5">
                      <span className="h-3.5 w-3.5 flex items-center justify-center text-[10px] font-bold font-mono">SC</span>
                      Saved Comparisons
                    </div>
                    <span className="text-[7px] text-brand-primary font-bold">[Soon]</span>
                  </div>

                  <Link
                    to="/settings"
                    onClick={() => setProfileDropdownOpen(false)}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-left text-brand-textMuted hover:text-brand-primary hover:bg-brand-primary/5 transition-all uppercase border-t border-brand-border/40 mt-1 pt-2"
                  >
                    <Settings className="h-3.5 w-3.5" />
                    Account Settings
                  </Link>

                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-left text-brand-danger hover:bg-brand-danger/5 transition-all mt-1.5 pt-2 border-t border-brand-border/40 uppercase cursor-pointer"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Terminate Session
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link
              to="/login"
              className="text-brand-primary border border-brand-primary px-3 py-1.5 hover:bg-brand-primary/10 transition-all font-mono"
            >
              [Login]
            </Link>
          )}
        </nav>

        {/* Right side: theme toggle on mobile (shown next to hamburger) */}
        <div className="sm:hidden flex items-center gap-2">
          <button
            onClick={() => setIsDark(!isDark)}
            className="p-2 border border-brand-border hover:border-brand-primary hover:text-brand-primary transition-all text-brand-textMuted rounded-md"
            aria-label={isDark ? 'Light Mode' : 'Dark Mode'}
          >
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {/* Page Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 pt-6 sm:pt-8">
        <Suspense fallback={
          <div className="h-[60vh] flex flex-col items-center justify-center text-brand-textMuted font-mono">
            <RefreshCw className="h-6 w-6 animate-spin text-brand-primary mb-3" />
            <p className="text-[10px] tracking-wider">COMPILING STOCK ENGINE MATRIX...</p>
          </div>
        }>
          <Routes>
            {/* Mutual Fund Routes (Default) */}
            <Route path="/" element={<Home />} />
            <Route path="/funds" element={<Home />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/funds/explorer" element={<Explorer />} />
            <Route path="/detail/:schemeCode" element={<Detail />} />
            <Route path="/funds/detail/:schemeCode" element={<Detail />} />

            {/* Stock Routes */}
            <Route path="/stocks" element={<StockHome />} />
            <Route path="/stocks/explorer" element={<StockExplorer />} />
            <Route path="/stocks/detail/:symbol" element={<StockDetail />} />
            <Route path="/stocks/sector/:sectorName" element={<StockSector />} />
            <Route path="/stocks/compare" element={<StockCompare />} />
            <Route path="/stocks/watchlist" element={<ProtectedRoute><StockWatchlist /></ProtectedRoute>} />
            <Route path="/news" element={<News />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          </Routes>
        </Suspense>
      </main>

      {/* Global Footer */}
      <footer className="border-t border-brand-border py-6 text-center mt-auto font-mono text-[9px] text-brand-textMuted bg-brand-surface">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row justify-between items-center gap-2">
          <p>© {new Date().getFullYear()} ALPHAMATRIX TERMINAL. ALL METRICS CALCULATED LOCAL_DB.</p>
          <p className="text-brand-primary uppercase">[RAG_GATEWAY: active // SECURE_CONSTRAINTS: forced]</p>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}
