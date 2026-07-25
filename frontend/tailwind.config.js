/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["Space Mono", "Menlo", "monospace"],
      },
      colors: {
        paper: "#FCFCFA",
        surface: "#FFFFFF",
        subtle: "#F1F4F1",
        line: "#E3E7E2",
        ink: "#14181A",
        muted: "#6B726C",
        green: {
          DEFAULT: "#1C7C55",
          soft: "#E7F2EB",
          bright: "#35C67C",
        },
        danger: "#C0402B",
        warn: "#B7791F",
      },
      borderColor: {
        DEFAULT: "#E3E7E2",
      },
    },
  },
  plugins: [],
};
