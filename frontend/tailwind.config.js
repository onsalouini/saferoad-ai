/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        page: v("page"),
        surface: v("surface"),
        raised: v("raised"),
        line: v("line"),
        ink: v("ink"),
        soft: v("soft"),
        muted: v("muted"),
        accent: v("accent"),
        "accent-strong": v("accent-strong"),
        good: v("good"),
        warning: v("warning"),
        serious: v("serious"),
        critical: v("critical"),
        up: v("up"),
        down: v("down"),
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', '"Segoe UI"', "Roboto", "sans-serif"],
      },
      maxWidth: { page: "76rem" },
    },
  },
  plugins: [],
}
