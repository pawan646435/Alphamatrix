

export default function StockLogo({ symbol, size = 'md' }) {
  const getLogoChar = (sym) => {
    if (!sym) return 'S';
    return sym.trim().toUpperCase().charAt(0);
  };

  const sizes = {
    sm: 'w-6 h-6 text-[10px]',
    md: 'w-8 h-8 text-[12px]',
    lg: 'w-12 h-12 text-[18px]'
  };

  const selectedSize = sizes[size] || sizes.md;

  const renderLogo = () => {
    const symUpper = (symbol || '').toUpperCase().trim();
    const strokeWidth = size === 'lg' ? 4 : 3;

    switch (symUpper) {
      case 'TCS':
      case 'TATAMOTORS':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full text-brand-primary" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 25 H80 M50 25 V80" />
            <path d="M35 80 H65" />
          </svg>
        );
      case 'INFY':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full text-brand-primary" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
            <path d="M30 20 H70 M50 20 V80 M30 80 H70" />
          </svg>
        );
      case 'HDFCBANK':
      case 'HAL':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full text-brand-primary" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
            <path d="M25 20 V80 M75 20 V80 M25 50 H75" />
          </svg>
        );
      case 'RELIANCE':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full text-brand-primary" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
            <path d="M30 80 V20 H55 C65 20, 65 45, 55 45 H30 M50 45 L70 80" />
          </svg>
        );
      default:
        return (
          <span className="font-semibold font-display tracking-tighter text-brand-primary uppercase">
            {getLogoChar(symbol)}
          </span>
        );
    }
  };

  return (
    <div className={`shrink-0 flex items-center justify-center rounded-lg border border-brand-primary/20 bg-brand-primary/5 select-none overflow-hidden ${selectedSize}`}>
      <div className="w-[70%] h-[70%] flex items-center justify-center">
        {renderLogo()}
      </div>
    </div>
  );
}
