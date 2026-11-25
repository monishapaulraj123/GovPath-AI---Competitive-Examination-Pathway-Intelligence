/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        gp: {
          primary: '#83529B',
          'primary-hover': '#704387',
          'primary-active': '#613774',
          'primary-light': '#F2EBF6',
          'primary-soft': '#EAE3F0',
          'primary-border': '#D8C5E3',
          bg: '#F7F6F8',
          surface: '#FFFFFF',
          ink: '#292633',
          'ink-secondary': '#6B6674',
          'ink-muted': '#8A8492',
          border: '#E5E1E8',
          divider: '#EAE7ED',
          success: '#15803D',
          'success-bg': '#EAF6EE',
          warning: '#B45309',
          'warning-bg': '#FFF5E6',
          error: '#DC2626',
          'error-bg': '#FDECEC',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
