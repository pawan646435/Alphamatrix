import React from 'react';

/**
 * AlphaMatrixLogo — self-contained SVG logo component.
 *
 * Props:
 *  size       — pixel size of the square container (default 36)
 *  showGlow   — whether to render the glow filter (default true)
 *  className  — extra class names on the wrapper div
 */
export default function AlphaMatrixLogo({ size = 36, showGlow = true, className = '' }) {
  // Unique IDs per instance to avoid SVG defs conflicts when rendered multiple times
  const uid = React.useId().replace(/:/g, '');
  const gradId = `am-gold-${uid}`;
  const bgId   = `am-bg-${uid}`;
  const glowId = `am-glow-${uid}`;

  return (
    <div
      className={`flex-shrink-0 ${className}`}
      style={{ width: size, height: size }}
      aria-label="AlphaMatrix logo"
      role="img"
    >
      <svg
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ width: '100%', height: '100%' }}
      >
        <defs>
          {/* Warm gold gradient */}
          <linearGradient id={gradId} x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#C9A56B"/>
            <stop offset="50%"  stopColor="#E8C97A"/>
            <stop offset="100%" stopColor="#F0D898"/>
          </linearGradient>

          {/* Dark container background */}
          <linearGradient id={bgId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%"   stopColor="#1E1A14"/>
            <stop offset="100%" stopColor="#0F0D0A"/>
          </linearGradient>

          {/* Soft glow for the alpha mark */}
          {showGlow && (
            <filter id={glowId} x="-25%" y="-25%" width="150%" height="150%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="2.8" result="blur"/>
              <feComposite in="SourceGraphic" in2="blur" operator="over"/>
            </filter>
          )}
        </defs>

        {/* ── Container: rounded square with premium border ── */}
        <path
          d="M13 4 L87 4 Q96 4 96 13 L96 87 Q96 96 87 96 L13 96 Q4 96 4 87 L4 13 Q4 4 13 4 Z"
          fill={`url(#${bgId})`}
        />
        <path
          d="M13 4 L87 4 Q96 4 96 13 L96 87 Q96 96 87 96 L13 96 Q4 96 4 87 L4 13 Q4 4 13 4 Z"
          stroke={`url(#${gradId})`}
          strokeWidth="1.5"
          fill="none"
          opacity="0.65"
        />

        {/* ── Matrix dot grid: 3×3 ── */}
        {/* Row 1 */}
        <circle cx="28" cy="28" r="2" fill={`url(#${gradId})`} opacity="0.30"/>
        <circle cx="50" cy="28" r="2" fill={`url(#${gradId})`} opacity="0.18"/>
        <circle cx="72" cy="28" r="2" fill={`url(#${gradId})`} opacity="0.30"/>
        {/* Row 2 */}
        <circle cx="28" cy="50" r="2" fill={`url(#${gradId})`} opacity="0.18"/>
        <circle cx="50" cy="50" r="2" fill={`url(#${gradId})`} opacity="0.28"/>
        <circle cx="72" cy="50" r="2" fill={`url(#${gradId})`} opacity="0.18"/>
        {/* Row 3 */}
        <circle cx="28" cy="72" r="2" fill={`url(#${gradId})`} opacity="0.30"/>
        <circle cx="50" cy="72" r="2" fill={`url(#${gradId})`} opacity="0.18"/>
        <circle cx="72" cy="72" r="2" fill={`url(#${gradId})`} opacity="0.30"/>

        {/* ── Alpha (α) mark ── */}
        {/* Glow pass */}
        {showGlow && (
          <path
            filter={`url(#${glowId})`}
            opacity="0.45"
            d="M 75 27.5 L 62.5 50 C 50 72.5, 25 72.5, 25 50 C 25 27.5, 50 27.5, 62.5 50 L 75 72.5"
            stroke={`url(#${gradId})`}
            strokeWidth="7"
            strokeLinecap="round"
            fill="none"
          />
        )}
        {/* Sharp pass */}
        <path
          d="M 75 27.5 L 62.5 50 C 50 72.5, 25 72.5, 25 50 C 25 27.5, 50 27.5, 62.5 50 L 75 72.5"
          stroke={`url(#${gradId})`}
          strokeWidth="5.5"
          strokeLinecap="round"
          fill="none"
        />

        {/* ── Corner terminal ticks ── */}
        <path
          d="M 10 19 L 10 10 L 19 10"
          stroke={`url(#${gradId})`}
          strokeWidth="1.8"
          strokeLinecap="square"
          fill="none"
          opacity="0.45"
        />
        <path
          d="M 90 81 L 90 90 L 81 90"
          stroke={`url(#${gradId})`}
          strokeWidth="1.8"
          strokeLinecap="square"
          fill="none"
          opacity="0.45"
        />
      </svg>
    </div>
  );
}
