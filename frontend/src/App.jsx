import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { LayoutDashboard, Compass, Cpu, Terminal, Sun, Moon } from 'lucide-react';
import Home from './pages/Home';
import Explorer from './pages/Explorer';
import Detail from './pages/Detail';

export default function App() {
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved ? saved === 'true' : true; // Default to dark mode
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('darkMode', String(isDark));
  }, [isDark]);

  return (
    <Router>
      <div className="min-h-screen flex flex-col selection:bg-brand-primary selection:text-brand-bg bg-brand-bg text-black dark:text-white transition-colors duration-300">
        {/* Global Console Navigation Bar */}
        <header className="sticky top-0 z-50 px-6 py-4 flex justify-between items-center bg-brand-bg/95 backdrop-blur-md border-b border-brand-border shadow-md">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 border border-brand-primary/30 rounded-lg flex items-center justify-center bg-brand-primary/5 group-hover:border-brand-primary group-hover:shadow-[0_0_15px_rgba(201,165,107,0.25)] transition-all duration-300">
              <svg 
                viewBox="0 0 100 100" 
                className="w-6.5 h-6.5 text-brand-primary"
                fill="none" 
                xmlns="http://www.w3.org/2000/svg"
              >
                <defs>
                  <linearGradient id="logo-grad" x1="0%" y1="100%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#ff7b00" />
                    <stop offset="100%" stopColor="#ffae00" />
                  </linearGradient>
                </defs>
                {/* Matrix grid overlay */}
                <line x1="20" y1="10" x2="20" y2="90" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                <line x1="40" y1="10" x2="40" y2="90" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                <line x1="60" y1="10" x2="60" y2="90" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                <line x1="80" y1="10" x2="80" y2="90" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                <line x1="10" y1="20" x2="90" y2="20" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                <line x1="10" y1="40" x2="90" y2="40" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                <line x1="10" y1="60" x2="90" y2="60" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                <line x1="10" y1="80" x2="90" y2="80" stroke="currentColor" strokeWidth="1" opacity="0.1" />
                
                {/* Stylized Alpha (α) path acting as a rising trend line */}
                <path 
                  d="M15 70 C22 70, 32 30, 48 30 C64 30, 75 70, 80 70 C85 70, 90 55, 92 48" 
                  stroke="url(#logo-grad)" 
                  strokeWidth="7" 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                />
                
                {/* Upward trend arrow head */}
                <path 
                  d="M82 45 L92 48 L88 58" 
                  stroke="url(#logo-grad)" 
                  strokeWidth="6" 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                />
              </svg>
            </div>
            <span className="text-lg font-extrabold tracking-wider text-black dark:text-white font-display uppercase group-hover:text-brand-primary transition-colors">
              ALPHAMATRIX
            </span>
          </Link>
          
          <nav className="flex items-center gap-4 font-mono text-[10px] uppercase tracking-wider">
            <Link 
              to="/" 
              className="flex items-center gap-1.5 text-brand-textMuted hover:text-brand-primary border border-transparent hover:border-brand-primary px-3 py-1.5 transition-all"
            >
              <LayoutDashboard className="h-3.5 w-3.5 text-brand-primary" />
              [Dashboard]
            </Link>
            <Link 
              to="/explorer" 
              className="flex items-center gap-1.5 text-brand-textMuted hover:text-brand-primary border border-transparent hover:border-brand-primary px-3 py-1.5 transition-all"
            >
              <Compass className="h-3.5 w-3.5 text-brand-primary" />
              [Matrix Explorer]
            </Link>
            <button
              onClick={() => setIsDark(!isDark)}
              className="p-1.5 border border-brand-border hover:border-brand-primary hover:text-brand-primary transition-all flex items-center justify-center text-brand-textMuted"
              aria-label="Toggle Theme"
            >
              {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            </button>
          </nav>
        </header>

        {/* Page Container */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-6 pt-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/detail/:schemeCode" element={<Detail />} />
          </Routes>
        </main>

        {/* Global Footer (Console Telemetry style) */}
        <footer className="border-t border-brand-border py-6 text-center mt-auto font-mono text-[9px] text-brand-textMuted bg-brand-surface">
          <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row justify-between items-center gap-2">
            <p>© {new Date().getFullYear()} ALPHAMATRIX TERMINAL. ALL METRICS CALCULATED LOCAL_DB.</p>
            <p className="text-brand-primary uppercase">[RAG_GATEWAY: active // SECURE_CONSTRAINTS: forced]</p>
          </div>
        </footer>
      </div>
    </Router>
  );
}
