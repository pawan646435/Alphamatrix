

export default function FundLogo({ fundName, size = 'md' }) {
  // Extract AMC Name
  const getAMC = (name) => {
    if (!name) return { code: 'MF', display: 'MF' };
    const upper = name.toUpperCase();
    if (upper.includes('HDFC')) return { code: 'HDFC', display: 'H' };
    if (upper.includes('SBI')) return { code: 'SBI', display: 'S' };
    if (upper.includes('NIPPON')) return { code: 'NIPPON', display: 'N' };
    if (upper.includes('ICICI') || upper.includes('PRUDENTIAL')) return { code: 'ICICI', display: 'I' };
    if (upper.includes('AXIS')) return { code: 'AXIS', display: 'A' };
    if (upper.includes('QUANT')) return { code: 'QUANT', display: 'Q' };
    if (upper.includes('KOTAK')) return { code: 'KOTAK', display: 'K' };
    if (upper.includes('DSP')) return { code: 'DSP', display: 'D' };
    if (upper.includes('UTI')) return { code: 'UTI', display: 'U' };
    if (upper.includes('TATA')) return { code: 'TATA', display: 'T' };
    if (upper.includes('MIRAE')) return { code: 'MIRAE', display: 'M' };
    if (upper.includes('PARAG') || upper.includes('PPFAS')) return { code: 'PPFAS', display: 'PP' };
    if (upper.includes('MOTILAL') || upper.includes('MOSL')) return { code: 'MOTILAL', display: 'MO' };
    if (upper.includes('CANARA') || upper.includes('ROBECO')) return { code: 'CANARA', display: 'CR' };
    if (upper.includes('BANDHAN')) return { code: 'BANDHAN', display: 'B' };
    
    // Fallback: use first letter
    const firstWord = name.trim().split(' ')[0] || '';
    const letter = firstWord.charAt(0).toUpperCase();
    return { code: 'GENERIC', display: letter || 'F' };
  };

  const amc = getAMC(fundName);

  // Size configurations
  const sizes = {
    sm: 'w-6 h-6 text-[10px]',
    md: 'w-8 h-8 text-[12px]',
    lg: 'w-12 h-12 text-[18px]'
  };

  const selectedSize = sizes[size] || sizes.md;

  // Custom vector shapes for major AMCs
  const renderVector = () => {
    const strokeWidth = size === 'lg' ? 4 : 3;
    
    switch (amc.code) {
      case 'SBI':
        // Iconic circular keyhole shape
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full text-brand-primary" fill="none" stroke="currentColor" strokeWidth={strokeWidth * 1.5}>
            <circle cx="50" cy="50" r="32" />
            <circle cx="50" cy="50" r="10" fill="currentColor" />
            <line x1="50" y1="50" x2="50" y2="82" strokeLinecap="round" />
          </svg>
        );
      case 'QUANT':
        // Math Summation/Sigma symbol representing quantitative focus
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full text-brand-primary" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
            <path d="M72 25 H30 L52 50 L30 75 H72" />
          </svg>
        );
      case 'AXIS':
        // Modern minimalist chevron triangle
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full text-brand-primary" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
            <path d="M50 20 L80 80 H20 Z" />
            <line x1="50" y1="20" x2="50" y2="80" opacity="0.3" />
          </svg>
        );
      default:
        // Elegant Serif Monogram for others
        return (
          <span className="font-semibold font-display tracking-tighter text-brand-primary uppercase">
            {amc.display}
          </span>
        );
    }
  };

  return (
    <div className={`shrink-0 flex items-center justify-center rounded-lg border border-brand-primary/20 bg-brand-primary/5 select-none overflow-hidden ${selectedSize}`}>
      <div className="w-[70%] h-[70%] flex items-center justify-center">
        {renderVector()}
      </div>
    </div>
  );
}
