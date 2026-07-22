import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

// Dev proxy: the UI calls /api/*, Vite forwards to the FastAPI backend.
// No CORS holes, no hardcoded backend URL in app code (VITE_BACKEND_URL
// in .env.local overrides the proxy target; see .env.example).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: env.VITE_BACKEND_URL || "http://127.0.0.1:8000",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: false,
    },
  };
});
