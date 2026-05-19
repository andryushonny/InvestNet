/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0b0d12',
        panel: '#141821',
        border: '#23293a',
        muted: '#8a93a7',
        accent: '#5b8def',
        ok: '#3fb950',
        warn: '#d29922',
        err: '#f85149',
      },
    },
  },
  plugins: [],
};
