# Optional branding

The default interface is **Integration Governance**, with no organization name or
logo, a neutral favicon, and neutral action colors. Lifecycle colors remain
semantic and are paired with text labels.

Copy `frontend/.env.example` to `frontend/.env.local`, change the desired values,
and rebuild with `npm --prefix frontend run build`. These are standard Vite
build-time settings, not runtime backend settings. Exported environment variables
override dotenv files. All `VITE_*` values are public in browser bundles: never
put secrets in them.

| Setting | Default |
| --- | --- |
| `VITE_APP_NAME` | `Integration Governance` |
| `VITE_ORGANIZATION_NAME` | Empty, hidden |
| `VITE_LOGO_PATH` | Empty, hidden |
| `VITE_FAVICON_PATH` | `/favicon.svg` |
| `VITE_PRIMARY_COLOR` | `#374151` |
| `VITE_PRIMARY_DARK_COLOR` | `#1f2937` |
| `VITE_ACCENT_COLOR` | `#4b5563` |

Names are trimmed; an empty application name falls back to the default. The
application name controls the header's accessible home label and route titles.
The backend's existing `APP_NAME` setting controls API documentation separately;
set both names alike when customizing them.

Place optional artwork in `frontend/public`, for example
`frontend/public/organization-logo.svg`, then configure
`VITE_LOGO_PATH=/organization-logo.svg`. Use absolute same-origin paths, without
query strings or fragments. External URLs, protocol-relative URLs, data URLs,
backslashes and whitespace are rejected. A failed logo request hides the image
while keeping the textual identity. Keep `/favicon.svg` as the neutral fallback;
use a different filename for a custom favicon. Verify that custom assets actually
load in the deployed application.

Quote six-digit hex colors in dotenv files, for example
`VITE_PRIMARY_COLOR="#123456"`. Invalid colors and colors with less than 4.5:1
contrast against white fall back to neutral defaults. Focus and lifecycle colors
are not overridden. Inspect the completed deployment for accessibility, including
custom artwork and long names on narrow screens.

## Checks

Run `npm --prefix frontend run test:branding` for Node's built-in configuration
tests (a Node version supporting `--experimental-strip-types` is required), plus
frontend typecheck and build. Browser tests load the same production Vite
configuration, including `.env.local`. Run `npm --prefix frontend run test:e2e`
after building with the same settings. The missing-logo case is skipped when no
logo is configured. For custom-build coverage, set an optional logo path and
custom names before both build and test. The identity test supplies an image
fixture; the missing-logo test aborts that image request. These tests do not
replace checking that real deployment artwork is present.

Keep the full repository gate and release checks mandatory. Restore neutral
settings and rebuild before packaging a neutral distribution.
