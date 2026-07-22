/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {},
  },
  safelist: [
    { pattern: /^(bg|border)-(blue|orange|green|red)-(50|200)$/ },
  ],
  plugins: [],
};
