import { useState, useEffect, useCallback } from 'react';
import { 
  RefreshCw, Zap, X, ExternalLink, 
  TrendingUp, TrendingDown, Minus, Filter, AlertTriangle 
} from 'lucide-react';
import apiClient from '../services/api';
import { NewsCardSkeleton } from '../components/skeletons/Skeletons';

const CATEGORIES = [
  { id: 'all', label: 'All Feeds' },
  { id: 'stocks', label: 'Stocks' },
  { id: 'mutual_funds', label: 'Mutual Funds' },
  { id: 'economy', label: 'Economy' },
  { id: 'policy', label: 'Policy & Gov' },
  { id: 'earnings', label: 'Earnings' }
];

export default function News() {
  const [activeStream, setActiveStream] = useState('india'); // Default to India stream
  const [category, setCategory] = useState('all');
  const [indiaNews, setIndiaNews] = useState([]);
  const [globalNews, setGlobalNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // AI Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [loadingStep, setLoadingStep] = useState(0);

  // Fetch news feeds (fetches both streams concurrently)
  const fetchNews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [indiaRes, globalRes] = await Promise.all([
        apiClient.get('/news/list', { params: { stream: 'india', category } }),
        apiClient.get('/news/list', { params: { stream: 'global', category } })
      ]);
      setIndiaNews(indiaRes.data || []);
      setGlobalNews(globalRes.data || []);
    } catch (err) {
      console.error('Failed to fetch news feeds', err);
      setError('Failed to fetch news feeds. Please check your backend connection.');
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    setTimeout(() => fetchNews(), 0);
  }, [fetchNews]);

  // Loading steps animation for AI
  useEffect(() => {
    let interval;
    if (analysisLoading) {
      setTimeout(() => setLoadingStep(0), 0);
      interval = setInterval(() => {
        setLoadingStep(prev => (prev + 1) % 3);
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [analysisLoading]);

  // Trigger on-demand AI impact analysis
  const handleAnalyze = async (article) => {
    setSelectedArticle(article);
    setDrawerOpen(true);
    setAnalysis(null);
    setAnalysisError(null);
    setAnalysisLoading(true);

    try {
      const response = await apiClient.post('/news/analyze', {
        title: article.title,
        publisher: article.publisher,
        link: article.link
      });
      setAnalysis(response.data);
    } catch (err) {
      console.error('AI impact analysis failed', err);
      setAnalysisError('AI Analysis failed. Showing local heuristics or retry.');
    } finally {
      setAnalysisLoading(false);
    }
  };

  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => {
    const timer = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 60000);
    return () => clearInterval(timer);
  }, []);

  const getRelativeTime = (timestamp) => {
    if (!timestamp) return 'Recently';
    const diff = Math.max(0, now - timestamp);
    
    if (diff < 60) return 'Just now';
    const mins = Math.floor(diff / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const getImpactBadgeClass = (impact) => {
    switch (impact) {
      case 'HIGH':
        return 'bg-brand-danger/10 text-brand-danger border-brand-danger/25';
      case 'MEDIUM':
        return 'bg-brand-warning/10 text-brand-warning border-brand-warning/25';
      default:
        return 'bg-brand-border/20 text-brand-textMuted border-brand-border/40';
    }
  };

  const activeNewsList = activeStream === 'india' ? indiaNews : globalNews;

  return (
    <div className="max-w-4xl mx-auto space-y-6 sm:space-y-8 pb-20 relative min-h-screen">
      {/* Title Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-brand-border pb-4 animate-fade-in-up gap-4">
        <div>
          <span className="font-mono text-[10px] text-brand-primary tracking-widest uppercase">[MARKETS_INTELLIGENCE_CENTER]</span>
          <h1 className="text-3xl font-extrabold text-black dark:text-white tracking-wide uppercase font-display mt-1">NEWS INTEL</h1>
          <p className="text-xs text-brand-textMuted mt-1">
            Live institutional feeds aggregated from Yahoo Finance with on-demand AI Llama 3.3 impact diagnostics.
          </p>
        </div>
        <div className="flex gap-2 w-full md:w-auto shrink-0">
          <button 
            onClick={fetchNews} 
            disabled={loading}
            className="flex items-center justify-center gap-1.5 px-3 py-1.5 border border-brand-border hover:border-brand-primary hover:text-brand-primary text-xs font-mono transition-all rounded bg-brand-surface disabled:opacity-50 w-full md:w-auto"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            REFRESH_FEEDS
          </button>
        </div>
      </div>

      {/* Stream Tabs switcher */}
      <div className="flex bg-brand-surface border border-brand-border p-1 rounded-lg font-mono text-xs uppercase tracking-wider">
        <button
          onClick={() => setActiveStream('india')}
          className={`flex-1 py-3 min-h-[44px] text-center rounded-md transition-all font-bold ${
            activeStream === 'india'
              ? 'bg-brand-primary text-black shadow-sm font-extrabold'
              : 'text-brand-textMuted hover:text-black dark:hover:text-white'
          }`}
        >
          [ India Markets ]
        </button>
        <button
          onClick={() => setActiveStream('global')}
          className={`flex-1 py-3 min-h-[44px] text-center rounded-md transition-all font-bold ${
            activeStream === 'global'
              ? 'bg-brand-primary text-black shadow-sm font-extrabold'
              : 'text-brand-textMuted hover:text-black dark:hover:text-white'
          }`}
        >
          [ Global Markets ]
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-thin border-b border-brand-border/30">
        <Filter className="h-3.5 w-3.5 text-brand-primary shrink-0" />
        <span className="font-mono text-[9px] uppercase text-brand-textMuted mr-1 shrink-0 hidden sm:inline">Filter_Feed:</span>
        <div className="flex gap-2 shrink-0">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setCategory(cat.id)}
              className={`px-3 py-2 min-h-[36px] text-[10px] font-mono uppercase tracking-wider rounded border transition-all shrink-0 ${
                category === cat.id
                  ? 'border-brand-primary text-black bg-brand-primary font-bold'
                  : 'border-brand-border bg-brand-surface/40 text-brand-textMuted hover:border-brand-primary hover:text-brand-primary'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 border border-brand-danger/20 bg-brand-danger/5 rounded flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-brand-danger shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold text-brand-danger">Data Retrieval Exception</h4>
            <p className="text-xs text-brand-textMuted mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Loading State — skeleton cards matching real card dimensions */}
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <NewsCardSkeleton key={i} />
          ))}
        </div>
      ) : (
        /* Focused Single-Column News List Container */
        <div key={activeStream} className="space-y-4 animate-fade-in">
          <div className="flex items-center justify-between border-b border-brand-border/50 pb-2">
            <h3 className="text-md font-bold font-display uppercase tracking-wide flex items-center gap-2 text-black dark:text-white">
              <span className="w-2 h-2 rounded-full bg-brand-primary animate-pulse" />
              {activeStream === 'india' ? 'India Market Stream' : 'Global Market Stream'}
            </h3>
            <span className="font-mono text-[9px] text-brand-textMuted uppercase bg-brand-surface px-2 py-0.5 rounded border border-brand-border">
              {activeNewsList.length} FEEDS
            </span>
          </div>

          {activeNewsList.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-brand-border rounded font-mono text-xs text-brand-textMuted bg-brand-surface/20">
              {activeStream === 'india' ? '[NO_LIVE_INDIA_FEEDS_FOUND]' : '[NO_LIVE_GLOBAL_FEEDS_FOUND]'}
            </div>
          ) : (
            <div className="space-y-4">
              {activeNewsList.map((article, index) => (
                <NewsCard 
                  key={article.uuid || index} 
                  article={article} 
                  onAnalyze={handleAnalyze} 
                  getRelativeTime={getRelativeTime}
                  getImpactBadgeClass={getImpactBadgeClass}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* AI Drawer Backdrop */}
      {drawerOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 transition-opacity animate-fade-in"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      {/* AI Drawer Side-Panel */}
      <div className={`fixed top-0 right-0 h-full w-full sm:w-[500px] bg-brand-surface border-l border-brand-border z-50 shadow-2xl transition-transform duration-300 ease-out transform ${
        drawerOpen ? 'translate-x-0' : 'translate-x-full'
      } flex flex-col`}>
        
        {/* Drawer Header */}
        <div className="p-4 sm:p-6 border-b border-brand-border flex justify-between items-center bg-brand-bg/50">
          <div>
            <span className="font-mono text-[9px] text-brand-primary tracking-widest uppercase">[ALPHA_INTELLIGENCE_REPORT]</span>
            <h3 className="text-md font-bold font-display uppercase tracking-wide text-black dark:text-white mt-1">Market Impact Audit</h3>
          </div>
          <button 
            onClick={() => setDrawerOpen(false)}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center border border-brand-border hover:border-brand-primary hover:text-brand-primary transition-all rounded"
            aria-label="Close analysis panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {selectedArticle && (
            <div className="space-y-2">
              <span className="font-mono text-[9px] text-brand-textMuted">{selectedArticle.publisher.toUpperCase()} // {getRelativeTime(selectedArticle.timestamp)}</span>
              <h4 className="text-md font-extrabold text-black dark:text-white font-display uppercase leading-snug">{selectedArticle.title}</h4>
              <a 
                href={selectedArticle.link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[10px] font-mono text-brand-primary hover:text-brand-primaryHover transition-all mt-1"
              >
                OPEN_SOURCE_ARTICLE <ExternalLink className="h-2.5 w-2.5" />
              </a>
            </div>
          )}

          {/* AI Loader */}
          {analysisLoading && (
            <div className="py-12 flex flex-col items-center justify-center space-y-4">
              <div className="relative w-12 h-12">
                <div className="absolute inset-0 rounded-full border-2 border-brand-primary/20 animate-ping" />
                <div className="absolute inset-0 rounded-full border-2 border-brand-primary border-t-transparent animate-spin" />
              </div>
              <div className="text-center">
                <p className="text-xs font-mono text-brand-primary mt-2">
                  {loadingStep === 0 && '[DECOMPOSING_ARTICLE_HEADLINE]'}
                  {loadingStep === 1 && '[ROUTING_LLAMA_3.3_VIA_GROQ]'}
                  {loadingStep === 2 && '[SYNTHESIZING_IMPACT_REPORT]'}
                </p>
                <p className="text-[10px] text-brand-textMuted mt-1">Processing raw financial telemetry...</p>
              </div>
            </div>
          )}

          {/* AI Error */}
          {analysisError && (
            <div className="p-4 border border-brand-danger/20 bg-brand-danger/5 rounded flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-brand-danger mt-0.5 shrink-0" />
              <div className="text-xs">
                <span className="font-bold text-brand-danger block">Analysis Fetch Fault</span>
                <span className="text-brand-textMuted mt-1 block">{analysisError}</span>
              </div>
            </div>
          )}

          {/* AI Success Data */}
          {!analysisLoading && analysis && (
            <div className="space-y-6 animate-fade-in">
              
              {/* Verdict Indicator Header */}
              <div className="border border-brand-border p-4 bg-brand-bg/30 rounded flex justify-between items-center">
                <span className="font-mono text-[10px] uppercase text-brand-textMuted">Estimated Impact Direction</span>
                <span className={`flex items-center gap-1.5 px-3 py-1 font-mono text-xs uppercase rounded border ${
                  analysis.direction?.toLowerCase() === 'bullish'
                    ? 'bg-brand-success/10 text-brand-success border-brand-success/20 font-bold'
                    : analysis.direction?.toLowerCase() === 'bearish'
                    ? 'bg-brand-danger/10 text-brand-danger border-brand-danger/20 font-bold'
                    : 'bg-brand-border/20 text-brand-textMuted border-brand-border/40'
                }`}>
                  {analysis.direction?.toLowerCase() === 'bullish' && <TrendingUp className="h-3 w-3" />}
                  {analysis.direction?.toLowerCase() === 'bearish' && <TrendingDown className="h-3 w-3" />}
                  {analysis.direction?.toLowerCase() === 'neutral' && <Minus className="h-3 w-3" />}
                  {analysis.direction || 'NEUTRAL'}
                </span>
              </div>

              {/* Brief Summary */}
              <div className="space-y-2">
                <span className="font-mono text-[9px] text-brand-primary uppercase tracking-wider block">// Executive Briefing</span>
                <p className="text-xs text-black dark:text-white leading-relaxed font-sans">{analysis.summary}</p>
              </div>

              {/* Affected Sectors */}
              <div className="space-y-3">
                <span className="font-mono text-[9px] text-brand-primary uppercase tracking-wider block">// Impacted Sectors</span>
                <div className="space-y-3">
                  {analysis.affected_sectors?.map((sec, i) => (
                    <div key={i} className="border border-brand-border p-3.5 bg-brand-surface/40 hover:border-brand-primary/40 transition-all rounded space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-bold text-black dark:text-white uppercase font-display">{sec.sector}</span>
                        <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border ${
                          sec.impact?.toLowerCase() === 'positive'
                            ? 'bg-brand-success/10 text-brand-success border-brand-success/20'
                            : sec.impact?.toLowerCase() === 'negative'
                            ? 'bg-brand-danger/10 text-brand-danger border-brand-danger/20'
                            : 'bg-brand-border/20 text-brand-textMuted border-brand-border/40'
                        }`}>
                          {sec.impact}
                        </span>
                      </div>
                      <p className="text-[11px] text-brand-textMuted leading-relaxed">{sec.reason}</p>
                    </div>
                  ))}
                  {(!analysis.affected_sectors || analysis.affected_sectors.length === 0) && (
                    <span className="text-xs font-mono text-brand-textMuted">[NO_SECTOR_IMPACT_TELEMETRY]</span>
                  )}
                </div>
              </div>

              {/* Key Companies */}
              <div className="space-y-3">
                <span className="font-mono text-[9px] text-brand-primary uppercase tracking-wider block">// Equity Telemetry</span>
                <div className="space-y-3">
                  {analysis.key_companies?.map((co, i) => (
                    <div key={i} className="border border-brand-border p-3.5 bg-brand-surface/40 hover:border-brand-primary/40 transition-all rounded space-y-1">
                      <div className="flex justify-between items-center">
                        <div>
                          <span className="text-xs font-bold text-black dark:text-white uppercase font-display block">{co.company}</span>
                          <span className="text-[9px] font-mono text-brand-primary">{co.ticker}</span>
                        </div>
                        <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border ${
                          co.sentiment?.toLowerCase() === 'bullish'
                            ? 'bg-brand-success/10 text-brand-success border-brand-success/20'
                            : co.sentiment?.toLowerCase() === 'bearish'
                            ? 'bg-brand-danger/10 text-brand-danger border-brand-danger/20'
                            : 'bg-brand-border/20 text-brand-textMuted border-brand-border/40'
                        }`}>
                          {co.sentiment}
                        </span>
                      </div>
                      <p className="text-[11px] text-brand-textMuted leading-relaxed">{co.reason}</p>
                    </div>
                  ))}
                  {(!analysis.key_companies || analysis.key_companies.length === 0) && (
                    <span className="text-xs font-mono text-brand-textMuted">[NO_COMPANY_IMPACT_TELEMETRY]</span>
                  )}
                </div>
              </div>

            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Subcomponent: NewsCard
function NewsCard({ article, onAnalyze, getRelativeTime, getImpactBadgeClass }) {
  return (
    <div className="border border-brand-border bg-brand-surface hover:bg-brand-surface/70 transition-all p-4 sm:p-5 rounded duration-200 group relative flex flex-col justify-between min-h-[140px] hover:border-brand-primary hover:shadow-[0_4px_20px_-5px_rgba(201,165,107,0.12)]">
      <div>
        {/* Source metadata row */}
        <div className="flex justify-between items-center">
          <span className="font-mono text-[9px] text-brand-textMuted uppercase tracking-wider">
            {article.publisher.toUpperCase()} • {getRelativeTime(article.timestamp)}
          </span>
          <span className={`px-2 py-0.5 text-[8px] font-mono uppercase tracking-wider rounded border ${getImpactBadgeClass(article.impact)}`}>
            IMPACT: {article.impact}
          </span>
        </div>

        {/* Title */}
        <h4 className="text-sm font-extrabold text-black dark:text-white font-display mt-2 group-hover:text-brand-primary transition-colors duration-200 uppercase leading-snug">
          {article.title}
        </h4>
      </div>

      {/* Footer trigger */}
      <div className="flex justify-between items-center mt-4 pt-2 border-t border-brand-border/30 gap-2">
        <div>
          {article.link ? (
            <a 
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-3 py-2.5 min-h-[44px] text-[10px] font-mono uppercase text-brand-textMuted hover:text-brand-primary transition-all border border-transparent hover:border-brand-primary/45 rounded"
            >
              READ SOURCE ↗
            </a>
          ) : null}
        </div>
        <button 
          onClick={() => onAnalyze(article)}
          className="flex items-center gap-1.5 px-3 py-2.5 min-h-[44px] text-[10px] font-mono uppercase text-brand-primary hover:text-black dark:hover:text-black hover:bg-brand-primary transition-all border border-brand-primary/40 hover:border-brand-primary rounded"
        >
          <Zap className="h-3.5 w-3.5 animate-pulse-subtle fill-current" />
          Analyze
        </button>
      </div>
    </div>
  );
}
