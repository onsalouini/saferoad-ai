import { defineConfig, devices } from "@playwright/test"

// Tests de bout en bout du frontend. L'API est simulée dans les tests (page.route) :
// ils ne dépendent ni du backend, ni des services externes (OSRM, météo, OpenStreetMap).
const PORT = 5179
// CI : Chromium de Playwright ; en local, PW_CHANNEL=msedge utilise Edge déjà installé
const CHANNEL = process.env.PW_CHANNEL || "chromium"

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    serviceWorkers: "block",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: CHANNEL } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: CHANNEL } },
  ],
  webServer: {
    command: `npx vite --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    env: { VITE_API_URL: "http://api.test" },
  },
})
