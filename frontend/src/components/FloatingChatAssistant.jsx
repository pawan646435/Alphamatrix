import React, { useEffect } from 'react';
import { MessageSquare } from 'lucide-react';

// Shared floating AI chat drawer used on the Funds and Stocks home pages.
// On mobile the open state behaves as a docked bottom sheet with a backdrop
// so the panel never silently overlaps page content while scrolling.
export default function FloatingChatAssistant({
  title,
  emptyStateText,
  placeholder,
  chatOpen,
  setChatOpen,
  messages,
  chatLoading,
  chatMessage,
  setChatMessage,
  onSubmit,
}) {
  useEffect(() => {
    if (!chatOpen) return;
    const isMobile = window.matchMedia('(max-width: 639px)').matches;
    if (!isMobile) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prevOverflow; };
  }, [chatOpen]);

  return (
    <>
      {chatOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 sm:hidden"
          onClick={() => setChatOpen(false)}
          aria-hidden="true"
        />
      )}
      <div className={`fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50 transition-all duration-300 ${chatOpen ? 'w-[calc(100vw-32px)] sm:w-[360px] h-[70vh] sm:h-[480px]' : 'w-12 h-12'}`}>
        {chatOpen ? (
          <div className="w-full h-full bg-brand-surface border border-brand-border shadow-2xl flex flex-col overflow-hidden font-mono">
            <div className="bg-brand-bg border-b border-brand-border px-4 py-3 flex justify-between items-center text-xs">
              <div className="flex items-center gap-1.5 font-display">
                <span className="w-2 h-2 rounded-full bg-brand-primary animate-pulse" />
                <span className="font-bold text-black dark:text-white">{title}</span>
              </div>
              <button
                onClick={() => setChatOpen(false)}
                className="text-brand-textMuted hover:text-brand-primary font-bold"
              >
                [MIN]
              </button>
            </div>

            <div className="flex-1 p-4 overflow-y-auto space-y-4 scrollbar text-[11px] leading-relaxed">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-brand-textMuted px-2 space-y-2">
                  <MessageSquare className="h-6 w-6 opacity-30 text-brand-primary" />
                  <p className="text-[10px]">{emptyStateText}</p>
                </div>
              ) : (
                messages.map((m, idx) => (
                  <div
                    key={idx}
                    className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] border px-3 py-2 ${
                        m.role === 'user'
                          ? 'bg-brand-primary/10 border-brand-primary text-black dark:text-white'
                          : 'bg-brand-bg border-brand-border text-black dark:text-white'
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-brand-bg border border-brand-border px-3 py-2 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce" />
                    <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce [animation-delay:0.2s]" />
                    <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce [animation-delay:0.4s]" />
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={onSubmit} className="p-3 bg-brand-bg border-t border-brand-border flex gap-2">
              <input
                type="text"
                inputMode="text"
                placeholder={placeholder}
                value={chatMessage}
                onChange={(e) => setChatMessage(e.target.value)}
                className="flex-1 bg-brand-surface border border-brand-border px-3 py-2 min-h-[44px] text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary"
              />
              <button
                type="submit"
                disabled={chatLoading}
                className="bg-brand-primary hover:bg-brand-primaryHover disabled:opacity-50 text-black font-extrabold text-[10px] px-3 min-h-[44px] transition-colors border border-brand-primary"
              >
                EXEC
              </button>
            </form>
          </div>
        ) : (
          <button
            onClick={() => setChatOpen(true)}
            className="w-full h-full bg-brand-primary hover:bg-brand-primaryHover text-black flex items-center justify-center shadow-2xl transition-all border border-brand-primary hover:scale-105"
          >
            <MessageSquare className="h-5 w-5" />
          </button>
        )}
      </div>
    </>
  );
}
