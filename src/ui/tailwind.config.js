/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        vpg: {
          navy: '#1B2A4A',
          blue: '#2E75B6',
          accent: '#E8792F',
          light: '#F0F4F8',
        },
      },
    },
  },
  plugins: [],
}
