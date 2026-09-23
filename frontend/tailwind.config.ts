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
      keyframes: {
        "dash-fade-up": {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "dash-fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "dash-scale-in": {
          "0%": { opacity: "0", transform: "scale(0.94)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "dash-float": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
        "dash-shimmer": {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        "dash-pulse-soft": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.85", transform: "scale(1.04)" },
        },
      },
      animation: {
        "dash-fade-up": "dash-fade-up 0.55s cubic-bezier(0.22, 1, 0.36, 1) both",
        "dash-fade-in": "dash-fade-in 0.45s ease-out both",
        "dash-scale-in": "dash-scale-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both",
        "dash-float": "dash-float 4s ease-in-out infinite",
        "dash-shimmer": "dash-shimmer 2.8s linear infinite",
        "dash-pulse-soft": "dash-pulse-soft 2.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
