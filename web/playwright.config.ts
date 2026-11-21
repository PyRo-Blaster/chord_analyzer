import { defineConfig } from "@playwright/test";

const API_PORT = 8010; // apart from the dev API on 8000, so a running dev server is never reused
const WEB_PORT = 5180;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    // The installed Chrome on this computer; in CI, set PLAYWRIGHT_CHANNEL=chromium.
    channel: process.env.PLAYWRIGHT_CHANNEL ?? "chrome",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `uv run --directory ../api jca-serve --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/instruments`,
      env: { JCA_FAKE_PIPELINE: "1", JCA_DATA_DIR: "../data/app-e2e", JCA_POLL_SECONDS: "0.2" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `pnpm exec vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { JCA_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
