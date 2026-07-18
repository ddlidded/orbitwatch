/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        orbit: {
          bg: 'var(--bg)',
          sidebar: 'var(--sidebar)',
          panel: 'var(--panel)',
          soft: 'var(--soft)',
          deep: 'var(--deep)',
          border: 'var(--border)',
          text: 'var(--text)',
          muted: 'var(--muted)',
          faint: 'var(--faint)',
          blue: 'var(--blue)',
          green: 'var(--green)',
          yellow: 'var(--yellow)',
          orange: 'var(--orange)',
          red: 'var(--red)',
          purple: 'var(--purple)',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
