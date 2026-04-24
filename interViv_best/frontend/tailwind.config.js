/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Instrument Serif'", "serif"],
        body: ["'Barlow'", "sans-serif"],
      },
      colors: {
        // Velorah dark palette
        background: "#FFFFFF",
        foreground: "#000000",
        muted: "#6F6F6F",
        // Light UI tokens (used by Upload/Interview)
        ink: "#10212b",
        mist: "#e8f1ef",
        sand: "#f8efe4",
        ember: "#f26a4b",
        moss: "#5b8a72",
        ocean: "#246a73",
        gold: "#d7a54d",
      },
      boxShadow: {
        panel: "0 24px 80px rgba(16, 33, 43, 0.10)",
        glass: "0 28px 90px rgba(0,0,0,0.55)",
      },
      backgroundImage: {
        halo: "radial-gradient(circle at top left, rgba(242,106,75,0.22), transparent 38%), radial-gradient(circle at top right, rgba(36,106,115,0.18), transparent 32%), linear-gradient(135deg, rgba(255,255,255,0.94), rgba(232,241,239,0.84))",
      },
    },
  },
  plugins: [],
};
