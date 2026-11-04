/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
      },
      // One palette: every color points at the shared CSS tokens.
      colors: {
        background: "var(--color-background)",
        foreground: "var(--color-foreground)",
        muted: "var(--color-muted)",
        ink: "var(--color-ink)",
        surface: "var(--color-surface)",
        card: "var(--color-card)",
        line: "var(--color-border)",
        accent: "var(--color-accent)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
      },
    },
  },
  plugins: [],
};
