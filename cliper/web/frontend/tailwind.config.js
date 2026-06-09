/** @type {import('tailwindcss').Config} */
// Dark-studio token system: a near-black charcoal ramp ("ink"), one indigo accent, and
// semantic score colors. Kept deliberately small — one accent, no rainbow gradients.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0a0f", // app background
          900: "#0e0e14", // panels
          850: "#13131b",
          800: "#181821", // raised surface
          700: "#222230", // borders / hover
          600: "#2e2e3e",
          500: "#43435a",
          400: "#6b6b85",
          300: "#9a9ab0",
          200: "#c7c7d6",
          100: "#e8e8f0",
        },
        accent: {
          DEFAULT: "#6366f1", // indigo-500
          soft: "#818cf8",
          deep: "#4f46e5",
          glow: "rgba(99,102,241,0.35)",
        },
        good: "#34d399",
        warn: "#fbbf24",
        bad: "#f87171",
      },
      fontFamily: {
        sans: ['"Inter var"', "Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: { xl: "0.875rem", "2xl": "1.25rem" },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 30px -12px rgba(0,0,0,0.6)",
        glow: "0 0 0 1px rgba(99,102,241,0.4), 0 8px 30px -8px rgba(99,102,241,0.45)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: { shimmer: "shimmer 1.6s infinite" },
    },
  },
  plugins: [],
};
