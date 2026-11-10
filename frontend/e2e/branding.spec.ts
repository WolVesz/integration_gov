import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { loadEnv } from 'vite'
import { resolveBranding } from '../src/branding'

// Match the production build, including .env.local and exported overrides.
const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const branding = resolveBranding(loadEnv('production', frontendRoot, 'VITE_'))
const logoPathname = branding.logoPath ? new URL(branding.logoPath, 'http://localhost').pathname : ''
const faviconPathname = new URL(branding.faviconPath, 'http://localhost').pathname
const testIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><rect width="44" height="44" fill="#374151"/></svg>'

test('configured header, accessible navigation, route titles and mobile wrapping', async ({ page }) => {
  // Isolate rendering from deployment asset availability.
  await page.route(url => url.pathname === logoPathname || url.pathname === faviconPathname, route => route.fulfill({
    contentType: 'image/svg+xml', body: testIcon,
  }))
  await page.goto('/')
  const home = page.getByRole('link', { name: `${branding.appName} home`, exact: true })
  await expect(home).toBeVisible()
  await expect(home.locator('.app-title')).toHaveText(branding.appName)
  if (branding.logoPath) {
    await expect(home.locator('img')).toBeVisible()
    await expect(home.locator('img')).toHaveAttribute('src', branding.logoPath)
  } else {
    await expect(home.locator('img')).toHaveCount(0)
  }
  if (branding.organizationName) {
    await expect(home.locator('.brand-organization')).toHaveText(branding.organizationName)
  } else {
    await expect(home.locator('.brand-organization')).toHaveCount(0)
  }
  await expect(page).toHaveTitle(`Integrations — ${branding.appName}`)
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', branding.faviconPath)
  await expect(page.locator('html')).toHaveCSS('--color-primary', branding.primaryColor)
  await expect(page.locator('html')).toHaveCSS('--color-primary-dark', branding.primaryDarkColor)
  await expect(page.locator('html')).toHaveCSS('--color-accent', branding.accentColor)
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
  await page.goto('/not-a-page')
  await expect(page).toHaveTitle(`Not found — ${branding.appName}`)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.locator('.app-title').evaluate(element => { element.textContent = 'LongApplicationName'.repeat(12) })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test('custom identity keeps readable text when its logo is missing', async ({ page }) => {
  test.skip(!branding.logoPath, 'Requires a custom build with VITE_LOGO_PATH.')
  await page.route(url => url.pathname === logoPathname, route => route.abort())
  await page.goto('/')
  const home = page.getByRole('link', { name: `${branding.appName} home`, exact: true })
  await expect(home).toBeVisible()
  await expect(home.locator('.app-title')).toHaveText(branding.appName)
  await expect(home.locator('img')).toHaveCount(0)
  if (branding.organizationName) {
    await expect(home.locator('.brand-organization')).toHaveText(branding.organizationName)
  } else {
    await expect(home.locator('.brand-organization')).toHaveCount(0)
  }
  await expect(page).toHaveTitle(`Integrations — ${branding.appName}`)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})
