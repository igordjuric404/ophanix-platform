import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8088";
  const buildSourcemap = parseBuildSourcemap(env.VITE_BUILD_SOURCEMAP ?? env.BUILD_SOURCEMAP);

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 3000,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true
        },
        "/version": {
          target: apiTarget,
          changeOrigin: true
        }
      }
    },
    build: {
      outDir: "dist",
      sourcemap: buildSourcemap
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      globals: true,
      css: true
    }
  };
});

function parseBuildSourcemap(value: string | undefined): boolean | "hidden" | "inline" {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "true") {
    return true;
  }
  if (normalized === "hidden" || normalized === "inline") {
    return normalized;
  }
  return false;
}
