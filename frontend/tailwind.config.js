/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: { extend: { colors: { ink: '#0a0c1a', panel: '#111a27', line: '#243143', mint: '#9b9cff', muted: '#93a2b7' }, fontFamily: { sans: ['Figtree', 'sans-serif'], display: ['Sora', 'sans-serif'] } } },
  plugins: [],
}
