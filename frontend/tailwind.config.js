/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: 'var(--bg-color)',
          surface: 'var(--card-bg)',
          border: 'var(--border-color)',
          primary: 'var(--accent-gold)',
          primaryHover: 'var(--accent-gold-hover)',
          success: 'var(--accent-success)',
          danger: 'var(--accent-danger)',
          warning: 'var(--accent-warning)',
          textMuted: 'var(--text-muted)'
        }
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'sans-serif'],
        display: ['Syne', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.5s ease-out forwards',
      }
    },
  },
  plugins: [],
}
