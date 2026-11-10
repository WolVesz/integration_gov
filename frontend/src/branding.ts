/// <reference types="vite/client" />

/** Public build-time settings; never put secrets in VITE_* values. */
type BrandingEnv = Partial<Record<
  'VITE_APP_NAME' | 'VITE_ORGANIZATION_NAME' | 'VITE_LOGO_PATH' | 'VITE_FAVICON_PATH'
  | 'VITE_PRIMARY_COLOR' | 'VITE_PRIMARY_DARK_COLOR' | 'VITE_ACCENT_COLOR', string
>>

function assetPath(value: string | undefined, fallback: string): string {
  const path = value?.trim() ?? ''
  // Absolute same-origin paths only, never remote URLs or data URLs.
  return /^\/(?!\/)[^\\\s?#]*$/.test(path) ? path : fallback
}

function accessibleColor(value: string | undefined, fallback: string): string {
  const hex = value?.trim() ?? ''
  if (!/^#[\da-f]{6}$/i.test(hex)) return fallback
  // These colors appear against white; preserve WCAG AA text contrast.
  const channels = [1, 3, 5].map(offset => {
    const channel = parseInt(hex.slice(offset, offset + 2), 16) / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  const luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
  return 1.05 / (luminance + 0.05) >= 4.5 ? hex : fallback
}

export function resolveBranding(env: BrandingEnv) {
  return {
    appName: env.VITE_APP_NAME?.trim() || 'Integration Governance',
    organizationName: env.VITE_ORGANIZATION_NAME?.trim() || '',
    logoPath: assetPath(env.VITE_LOGO_PATH, ''),
    faviconPath: assetPath(env.VITE_FAVICON_PATH, '/favicon.svg'),
    primaryColor: accessibleColor(env.VITE_PRIMARY_COLOR, '#374151'),
    primaryDarkColor: accessibleColor(env.VITE_PRIMARY_DARK_COLOR, '#1f2937'),
    accentColor: accessibleColor(env.VITE_ACCENT_COLOR, '#4b5563'),
  }
}

const env = import.meta.env
export const branding = resolveBranding({
  VITE_APP_NAME: env?.VITE_APP_NAME,
  VITE_ORGANIZATION_NAME: env?.VITE_ORGANIZATION_NAME,
  VITE_LOGO_PATH: env?.VITE_LOGO_PATH,
  VITE_FAVICON_PATH: env?.VITE_FAVICON_PATH,
  VITE_PRIMARY_COLOR: env?.VITE_PRIMARY_COLOR,
  VITE_PRIMARY_DARK_COLOR: env?.VITE_PRIMARY_DARK_COLOR,
  VITE_ACCENT_COLOR: env?.VITE_ACCENT_COLOR,
})

export function applyBranding() {
  document.title = branding.appName
  const style = document.documentElement.style
  style.setProperty('--color-primary', branding.primaryColor)
  style.setProperty('--color-primary-dark', branding.primaryDarkColor)
  style.setProperty('--color-accent', branding.accentColor)
  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (favicon) {
    favicon.removeAttribute('type')
    favicon.href = branding.faviconPath
    favicon.onerror = () => {
      favicon.onerror = null
      favicon.href = '/favicon.svg'
    }
  }
}
