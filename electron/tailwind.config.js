/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/**/*.{html,tsx,ts}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0a0f',
          secondary: '#12121a',
          card: '#1a1a2e',
          hover: '#222240',
        },
        accent: {
          primary: '#00f0ff',
          xp: '#ffd700',
          success: '#00ff88',
          streak: '#ff6b35',
          level: '#a855f7',
          danger: '#ff4444',
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
        display: ['"Inter"', 'system-ui', 'sans-serif'],
      },
      animation: {
        'xp-fill': 'xpFill 1s ease-out forwards',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        xpFill: {
          '0%': { width: '0%' },
          '100%': { width: 'var(--xp-width)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 5px var(--glow-color)' },
          '50%': { boxShadow: '0 0 20px var(--glow-color)' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
