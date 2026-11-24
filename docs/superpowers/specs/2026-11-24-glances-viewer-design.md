# Glances viewer: design

Date: 2026-11-24. Status: approved in conversation (small project, short design).

## Intent

A kiosk page at `glances.subcult.tv` that shows each homelab host's Glances web UI. It can:

- show one host
- show all hosts on one screen
- show a chosen subset (a saved layout)
- rotate through any mix of these on a timer

Settings are edited in the page and saved on almaz, so a phone can change what the wall screen shows.

## Goals

- Kiosk first: full-screen, no chrome until the pointer moves.
- Settings UI: layouts, rotation order, seconds per slide.
- A rotation of one item stays put. Nothing reloads when a slide "switches" to itself.
- Switching slides never reloads a host's page.
- Small: one HTML file, one stdlib Python server, no build step, no dependencies.

## Non-goals

- Custom charts. The page embeds Glances' own UI.
- A UI for adding hosts. Hosts live in `config.json` and change rarely.
- Multiple users, per-user settings, or its own login. Authelia fronts the site.

## Constraints found

- Each host's Glances is reached through a Caddy site on almaz (`/opt/server/management/config/caddy/sites/`) that sent `X-Frame-Options DENY`. The change is `Content-Security-Policy: frame-ancestors https://glances.subcult.tv`.
- Glances backends accept only almaz (firewall), so the viewer is served through almaz's Caddy, via the existing Cloudflare tunnel wildcard `*.subcult.tv`.
- Authelia (`two_factor` for the Glances hosts) stays. A kiosk signs in once with "remember me" (one month).
- Hosts in scope: almaz, nuc, dozor, buran, kvant.

## Approaches

1. **Embed each host's Glances page in iframes (chosen).** Least code, real Glances UI. Cost: five pages running at once.
2. Draw own tiles from the Glances REST API. Compact and fully styled, but it is a second dashboard to build and maintain, and it needs the API proxied per host.
3. HTMX with server-rendered fragments. Swapping fragments would destroy iframes and reload them, which is the behaviour to avoid.

Settings storage: a small server on almaz saves `config.json` (chosen), rather than browser storage, so any device can edit what the kiosk shows.

## Design

**Display.** One iframe per host, created once and never moved or reloaded. A slide is a list of host ids. Showing a slide sets `display` and the CSS grid cell on the iframes in it and hides the rest. Grid is `ceil(sqrt(n))` columns; an incomplete last row's final tile spans the remaining columns.

**Slides.** A rotation is an ordered list of `{host: id}` or `{layout: id}`. The built-in layout `all` means every host. One slide, or a locally paused page, means no timer.

**Data.** `config.json`: `hosts` (`id`, `name`, `url`), `layouts` (`id`, `name`, `hosts`), `rotation`, `interval` (seconds, 5 to 3600).

**API.** `GET /api/config` (with `ETag`), `PUT /api/config` (JSON only; accepts `layouts`, `rotation`, `interval`; `hosts` are never taken from the client), `GET /healthz`. The page polls the config every 15 seconds and applies changes without reloading unchanged iframes.

**Controls.** A gear and prev/next/pause buttons fade in on pointer movement. Keys: left/right arrows, space to pause. Pause is local to that browser, not saved.

**Deploy.** One container `glances-viewer` on the `dev` network, behind Caddy at `glances.subcult.tv`. Config volume at `/data`.

## Left to the builder

Visual styling, validation messages, exact fade timings.
