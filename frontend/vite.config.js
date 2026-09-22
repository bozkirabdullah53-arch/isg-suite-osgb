import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const appBuildId =
  process.env.RENDER_GIT_COMMIT ||
  process.env.GITHUB_SHA ||
  process.env.SOURCE_VERSION ||
  `local-${Date.now()}`;

function stampServiceWorker() {
  return {
    name: "isg-suite-service-worker-build-stamp",
    closeBundle() {
      const swPath = path.resolve("dist/sw.js");
      if (!fs.existsSync(swPath)) return;
      const source = fs.readFileSync(swPath, "utf8");
      fs.writeFileSync(
        swPath,
        source.replaceAll("__ISG_SUITE_BUILD_ID__", appBuildId),
        "utf8",
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), stampServiceWorker()],
  define: {
    "import.meta.env.VITE_APP_BUILD_ID": JSON.stringify(appBuildId),
  },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.test.js"],
  },
});
