import { defineConfig, devices } from "@playwright/test";

// End-to-end smoke tests in a real browser (the installed Microsoft Edge locally, Playwright's Chromium on CI).
//   npm run e2e                                         saved runs only: no backend needed
//   E2E_API_URL=http://localhost:8000 npm run e2e       also the live tests, against a running API
const live = process.env.E2E_API_URL;
const port = live ? 5183 : 5182;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${port}`,
    channel: process.env.CI ? undefined : "msedge",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: process.env.CI ? undefined : "msedge" } },
    { name: "phone", use: { ...devices["Pixel 7"], channel: process.env.CI ? undefined : "msedge" }, grep: /@phone/ },
  ],
  webServer: {
    // The built site, as it will be deployed (the dev server re-bundles on a fresh install and reloads mid-test).
    command: `npx vite build --outDir dist-e2e --emptyOutDir && npx vite preview --outDir dist-e2e --port ${port} --strictPort`,
    port,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { VITE_API_URL: live ?? "" },
  },
});
