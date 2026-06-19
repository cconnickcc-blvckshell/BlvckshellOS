import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#080810",
        surface: "#0F0F1A",
        border: "#1A1A2E",
        primary: "#7B2FBE",
        active: "#A855F7",
        glow: "#A855F7",
        "cyan-accent": "#22D3EE",
        "text-primary": "#E8E8F0",
        "text-secondary": "#6B6B8A",
        success: "#22C55E",
        warning: "#F59E0B",
        error: "#EF4444",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      keyframes: {
        breathe: {
          "0%, 100%": { opacity: "0.55", transform: "scale(0.92)" },
          "50%": { opacity: "1", transform: "scale(1.06)" },
        },
        "pulse-fast": {
          "0%, 100%": { opacity: "0.7", transform: "scale(0.96)" },
          "50%": { opacity: "1", transform: "scale(1.12)" },
        },
        "scan-sweep": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        radiate: {
          "0%": { transform: "scale(0.8)", opacity: "0.5" },
          "100%": { transform: "scale(1.4)", opacity: "0" },
        },
      },
      animation: {
        breathe: "breathe 3.2s ease-in-out infinite",
        "pulse-fast": "pulse-fast 1.1s ease-in-out infinite",
        radiate: "radiate 2s ease-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
