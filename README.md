# Glances viewer

A kiosk page for the homelab's Glances web UIs, served at `https://glances.subcult.tv` behind Authelia.

It shows one host, every host, or a saved layout of several hosts, and can rotate through any mix on a timer. A rotation of one slide stays on screen and never reloads. Hover or touch the page to see the controls: previous, pause, next and settings (⚙). Keys: left and right arrows, space to pause (pause applies to that browser only). Settings are saved on the server, so any device can change what the wall screen shows. The page checks for changes every 15 seconds.

## How it works

- `public/index.html`: the whole front end. It creates one iframe per host and never reloads it; a slide only shows or hides iframes and places them on a grid.
- `server.py`: Python standard library only. Serves the page and `GET`/`PUT /api/config`. The client can change `layouts`, `rotation` and `interval`, but never `hosts`.
- `config.default.json`: the five hosts and a default rotation of one "all hosts" slide. Copied to `data/config.json` on first start.

## Changing hosts

Edit `data/config.json` on the server (the `hosts` list: `id`, `name`, `url`). The next poll picks it up. Each host's Caddy site must allow framing from this page: replace `X-Frame-Options DENY` with `Content-Security-Policy "frame-ancestors https://glances.subcult.tv"`.

## Run locally

```
DATA_DIR=./data PORT=8080 python3 server.py
python3 -m unittest
```

Locally the iframes point at the real hosts, which need an Authelia login and the framing header above. For a local try-out, edit `hosts` in `data/config.json` to point at any pages.

## Deploy (almaz)

`docker compose up -d --build` in `/opt/server/projects/glances-viewer`, on the external `management` network. Caddy:

```
http://glances.subcult.tv {
	import authelia
	reverse_proxy glances-viewer:8080
}
```

The Cloudflare tunnel already sends `*.subcult.tv` to Caddy. Authelia treats `glances.subcult.tv` as `two_factor`. A kiosk signs in once with "remember me", which lasts a month; if the session expires, the page reloads to Authelia's login.
