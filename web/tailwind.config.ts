import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0c11",
        panel: "#10131a",
        raised: "#161a23",
        line: "#232836",
        ink: "#e7e9ef",
        mute: "#8a92a6",
        accent: "#8b9cff",
        stale: "#f2a93b",
        ok: "#46d39a",
        bad: "#f0706a",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [],
} satisfies Config;
