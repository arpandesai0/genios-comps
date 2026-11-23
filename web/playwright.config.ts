import { defineConfig, devices } from "@playwright/test";

// E2E_PORT lets the mock dev server run beside a stack already on port 3000.
const port = process.env.E2E_PORT || "3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
      },
    },
  ],
  webServer: {
    command: `npm run dev -- --hostname 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_USE_MOCKS: "1", NEXT_TELEMETRY_DISABLED: "1" },
    timeout: 120_000,
  },
});
