import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const databasePath = join(tmpdir(), `integration-gov-browser-${process.pid}.sqlite`).replaceAll('\\', '/')

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:8766', trace: 'retain-on-failure', screenshot: 'only-on-failure',
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH },
  },
  webServer: {
    command: 'uv run --locked python -m uvicorn backend.main:app --host 127.0.0.1 --port 8766',
    cwd: fileURLToPath(new URL('..', import.meta.url)),
    env: {
      DEV_MODE: 'true',
      DEV_USER_EMAIL: 'browser.test@example.com',
      DEV_USER_NAME: 'Browser Test',
      DEV_USER_ROLE: 'integration',
      DATABASE_URL: `sqlite:///${databasePath}`,
      // Explicit blanks also override .env values; tests must never reach live services.
      LAKEBASE_INSTANCE_NAME: '',
      PGHOST: '',
      EMBEDDING_ENDPOINT: '',
    },
    url: 'http://127.0.0.1:8766/healthz',
    reuseExistingServer: false,
  },
})
