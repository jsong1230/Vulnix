import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    // Next.js 프록시를 통해 API가 라우팅되므로 쿠키 허용
    extraHTTPHeaders: {},
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // 로컬 dev 서버 자동 시작
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
