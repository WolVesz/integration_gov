import assert from 'node:assert/strict'
import test from 'node:test'
import { resolveBranding } from '../src/branding.ts'

test('neutral defaults and blank names', () => {
  const defaults = resolveBranding({})
  assert.equal(defaults.appName, 'Integration Governance')
  assert.equal(defaults.organizationName, '')
  assert.equal(defaults.logoPath, '')
  assert.equal(defaults.faviconPath, '/favicon.svg')
  assert.equal(resolveBranding({ VITE_APP_NAME: '  ' }).appName, defaults.appName)
})

test('explicit identity and same-origin assets are configurable', () => {
  assert.deepEqual(resolveBranding({
    VITE_APP_NAME: ' Service Catalog ', VITE_ORGANIZATION_NAME: ' Example Organization ',
    VITE_LOGO_PATH: '/assets/logo.svg', VITE_FAVICON_PATH: '/assets/icon.png',
    VITE_PRIMARY_COLOR: '#123456', VITE_PRIMARY_DARK_COLOR: '#112233', VITE_ACCENT_COLOR: '#654321',
  }), {
    appName: 'Service Catalog', organizationName: 'Example Organization',
    logoPath: '/assets/logo.svg', faviconPath: '/assets/icon.png',
    primaryColor: '#123456', primaryDarkColor: '#112233', accentColor: '#654321',
  })
})

test('invalid or low-contrast colors fall back', () => {
  for (const value of ['red; display:none', 'var(--missing)', '#ffffff', '#123', 'transparent', '']) {
    const config = resolveBranding({ VITE_PRIMARY_COLOR: value, VITE_PRIMARY_DARK_COLOR: value, VITE_ACCENT_COLOR: value })
    assert.equal(config.primaryColor, '#374151')
    assert.equal(config.primaryDarkColor, '#1f2937')
    assert.equal(config.accentColor, '#4b5563')
  }
})

test('external and malformed asset paths use safe fallbacks', () => {
  for (const path of ['https://example.test/logo.svg', '//example.test/logo.svg', '/\\example.test/logo.svg', 'data:image/svg+xml,x', '/bad path.svg']) {
    assert.equal(resolveBranding({ VITE_LOGO_PATH: path }).logoPath, '')
    assert.equal(resolveBranding({ VITE_FAVICON_PATH: path }).faviconPath, '/favicon.svg')
  }
})
