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
        "ai-orb-float": {
          "0%, 100%": { transform: "translateY(0) rotate(0deg) scale(1)" },
          "33%": { transform: "translateY(-8px) rotate(2deg) scale(1.03)" },
          "66%": { transform: "translateY(-3px) rotate(-1.5deg) scale(1.01)" },
        },
        "ai-orb-glow-pulse": {
          "0%, 100%": {
            boxShadow:
              "0 0 0 1px rgba(2, 152, 112, 0.14), 0 8px 28px -8px rgba(2, 152, 112, 0.4), 0 0 32px -4px rgba(16, 185, 129, 0.35)",
          },
          "50%": {
            boxShadow:
              "0 0 0 3px rgba(2, 152, 112, 0.28), 0 14px 40px -8px rgba(2, 152, 112, 0.55), 0 0 56px -2px rgba(16, 185, 129, 0.55)",
          },
        },
        "ai-panel-enter": {
          "0%": {
            opacity: "0",
            transform: "scale(0.92)",
            filter: "blur(6px)",
          },
          "60%": {
            opacity: "1",
            filter: "blur(0)",
          },
          "100%": {
            opacity: "1",
            transform: "scale(1)",
            filter: "blur(0)",
          },
        },
        "ai-panel-glow-burst": {
          "0%": { opacity: "0.85", transform: "scale(0.6)" },
          "100%": { opacity: "0", transform: "scale(1.35)" },
        },
        "ai-dot-bounce": {
          "0%, 80%, 100%": { transform: "translateY(0)", opacity: "0.45" },
          "40%": { transform: "translateY(-7px)", opacity: "1" },
        },
      },
      animation: {
        "dash-fade-up": "dash-fade-up 0.55s cubic-bezier(0.22, 1, 0.36, 1) both",
        "dash-fade-in": "dash-fade-in 0.45s ease-out both",
        "dash-scale-in": "dash-scale-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both",
        "dash-float": "dash-float 4s ease-in-out infinite",
        "dash-shimmer": "dash-shimmer 2.8s linear infinite",
        "dash-pulse-soft": "dash-pulse-soft 2.2s ease-in-out infinite",
        "ai-orb-float": "ai-orb-float 4.5s ease-in-out infinite",
        "ai-orb-glow-pulse": "ai-orb-glow-pulse 2.8s ease-in-out infinite",
        "ai-panel-enter": "ai-panel-enter 0.48s cubic-bezier(0.22, 1, 0.36, 1) both",
        "ai-panel-glow-burst": "ai-panel-glow-burst 0.55s ease-out both",
        "ai-dot-bounce": "ai-dot-bounce 1.05s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
