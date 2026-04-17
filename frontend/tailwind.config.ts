import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0a0a14",
          subtle: "#12122a",
          card: "#1a1a2e",
          elevated: "#23233f",
        },
        border: {
          DEFAULT: "#2a2a4a",
          strong: "#3a3a5a",
        },
        brand: {
          50: "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          800: "#5b21b6",
          900: "#4c1d95",
        },
        accent: {
          cyan: "#22d3ee",
          green: "#34d399",
          blue: "#60a5fa",
          pink: "#f472b6",
          amber: "#fbbf24",
        },
      },
      backgroundImage: {
        "gradient-brand":
          "linear-gradient(135deg, #667eea 0%, #764ba2 50%, #c471ed 100%)",
        "gradient-mesh":
          "radial-gradient(at 20% 10%, rgba(118,75,162,0.25) 0px, transparent 50%), radial-gradient(at 80% 30%, rgba(34,211,238,0.18) 0px, transparent 50%), radial-gradient(at 30% 80%, rgba(236,72,153,0.15) 0px, transparent 50%)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
        shimmer: "shimmer 2s linear infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
