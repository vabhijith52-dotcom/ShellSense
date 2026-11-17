import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--bg-page)",
        card: "var(--surface-card)",
        "card-border": "var(--border-card)",
        "hero-navy": "var(--hero-navy)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "brand-indigo": "var(--brand-indigo)",
        "brand-violet": "var(--brand-violet)",
        success: "var(--color-success)",
        danger: "var(--color-danger)",
        warning: "var(--color-warning)",
        surface: {
          elevated: "var(--surface-elevated)",
          subtle: "var(--surface-subtle)",
        },
      },
      borderRadius: {
        card: "20px",
        control: "12px",
        pill: "9999px",
      },
      boxShadow: {
        card: "0 10px 30px -5px rgba(99, 102, 241, 0.08)",
        "card-hover": "0 18px 40px -8px rgba(99, 102, 241, 0.16)",
        modal: "0 25px 50px -12px rgba(15, 23, 42, 0.25)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
