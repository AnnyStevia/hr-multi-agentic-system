import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fefefe",
          100: "#f0f2f5",
          200: "#e2e6ea",
          300: "#9aa4ae",
          500: "#029870",
          600: "#01785a",
          700: "#015c46",
          800: "#0f224a",
          900: "#0f224a",
        },
      },
    },
  },
  plugins: [],
};

export default config;
