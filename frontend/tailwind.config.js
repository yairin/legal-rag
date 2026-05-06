/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Heebo', 'Assistant', 'Arial', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#dde6ff',
          500: '#3b5bdb',
          600: '#2f4ac2',
          700: '#233aa9',
        },
      },
    },
  },
  plugins: [],
}
