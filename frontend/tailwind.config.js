/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'primary': '#000666',
        'primary-container': '#1a237e',
        'secondary': '#6f48b2',
        'secondary-container': '#b78efe',
        'surface': '#fbf8ff',
        'surface-container': '#efecf5',
        'surface-container-low': '#f5f2fb',
        'on-surface': '#1b1b21',
        'on-surface-variant': '#454652',
        'outline': '#767683',
        'outline-variant': '#c6c5d4',
        'error': '#ba1a1a',
        'error-container': '#ffdad6',
        'teal': '#00BFA5',
      },
      fontFamily: {
        heading: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
