import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// Same-origin API contract: in dev, forward the FastAPI routes to the local
// brain (app/run_phase8.py on :9000). In production the built dist is mounted
// at /ui/ on the same origin, so no proxy (and no CORS) is involved.
const API_ROUTES = [
  "/stats", "/network", "/risk", "/copilot", "/geo", "/search",
  "/entity", "/case", "/governed", "/audit", "/brief",
  "/anomaly", "/series", "/resolve", "/mo", "/geocode",
  "/district", "/officers", "/officer", "/absconding", "/fir", "/whoami",
]

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./", // dist is served from /ui/ — keep asset URLs relative
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_ROUTES.map((r) => [r, { target: "http://127.0.0.1:9000", changeOrigin: true }]),
    ),
  },
})
