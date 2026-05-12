import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    ...(!process.env.CI
      ? [
          {
            command:
              "cd ../backend && PYTHONPATH=. uvicorn src.main:app --host 0.0.0.0 --port 8000",
            url: "http://localhost:8000/api/v1/health",
            reuseExistingServer: true,
            timeout: 120 * 1000,
          },
        ]
      : []),
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120 * 1000,
      env: {
        REACT_APP_API_URL: process.env.CI
          ? "http://backend:8000/api/v1"
          : "http://localhost:8000/api/v1",
      },
    },
  ],
});
