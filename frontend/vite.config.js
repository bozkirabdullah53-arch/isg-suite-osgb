import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const appBuildId =
  process.env.RENDER_GIT_COMMIT ||
  process.env.GITHUB_SHA ||
  process.env.SOURCE_VERSION ||
  `local-${Date.now()}`;

export default defineConfig({
  plugins: [react()],
  define: {
    "import.meta.env.VITE_APP_BUILD_ID": JSON.stringify(appBuildId),
  },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.test.js"],
  },
});
