/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        obsidian: '#060d0c',
        vault: '#0a1614',
        teal: '#0EA5A4',
        mint: '#5eead4',
        ink: '#eafff8',
        muted: '#8fb3ab',
      },
      fontFamily: {
        display: ['"Clash Display"', 'sans-serif'],
        body: ['"Satoshi"', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
