# astrolog

Self-hosted, local-first astrology dashboard. Computes real-time planetary
positions, houses, aspects, moon phase, natal charts, and live transits using
the Swiss Ephemeris — no external APIs, no cloud, nothing leaves your LAN.

Built for a TrueNAS + Caddy + Home Assistant homelab, themed Catppuccin Mocha.

## What's inside

```
astrolog/
├── backend/
│   ├── astrology_engine.py   # calculation engine (pyswisseph)
│   ├── app.py                # Flask API + serves the frontend
│   └── requirements.txt
├── frontend/
│   ├── index.html            # dashboard
│   └── static/               # style.css, app.js (no CDNs, works offline)
├── homeassistant/
│   └── astrolog_package.yaml # REST sensors + example automation
├── data/                     # saved natal charts land here (volume)
├── ephe/                     # optional Swiss Ephemeris data files
├── Dockerfile
└── docker-compose.yml
```

Accuracy note: with no ephemeris files present, the app uses the built-in
Moshier model (~0.1 arcsecond planetary accuracy — orders of magnitude finer
than any astrological orb). For maximum precision or asteroid work, download
`sepl_18.se1`, `semo_18.se1`, and `seas_18.se1` from Astrodienst's ftp
directory and drop them into `ephe/`. Chiron requires the `seas` file and is
skipped gracefully without it.

License note: pyswisseph / Swiss Ephemeris are AGPL for non-commercial use.

## Deploy on TrueNAS (Docker Compose)

1. Copy this folder to your usual apps dataset, e.g.
   `/mnt/Storage/apps/astrolog`.

2. Edit `docker-compose.yml`: set `DEFAULT_LAT` / `DEFAULT_LON` to your home
   coordinates (they drive house cusps and the Ascendant for the live wheel).

3. Build and start:

   ```bash
   cd /mnt/Storage/apps/astrolog
   docker compose up -d --build
   ```

   ✓ Checkpoint: `docker compose ps` shows astrolog running;
   `curl -s http://localhost:5010/api/ha` returns JSON with your sun sign.

4. Open `http://<truenas-ip>:5010` — you should see the wheel, planet table,
   and aspects populate within a second.

   ✓ Checkpoint: the header moon pill shows the current phase, and the
   footer under the wheel shows ASC/MC for your location.

5. Add a natal chart in the "Natal charts" card (name, birth date/time, IANA
   timezone like `America/Chicago`, birth coordinates). Saving selects it,
   draws the natal ring inside the wheel (blue glyphs), and fills the
   "Transits to natal" table.

   ✓ Checkpoint: `cat data/charts.json` shows your saved chart. This file is
   the only state — include it in your backup job.

## Reverse proxy (Caddy)

Add to your Caddyfile alongside your other services:

​```
astro.example.com {
    reverse_proxy 10.10.10.x:5010
}
​```

With a wildcard certificate and split DNS (e.g. Tailscale), the same
hostname works on your LAN and remotely.

## Home Assistant

1. Copy `homeassistant/astrolog_package.yaml` into `config/packages/` and set
   the resource IP (or use the Caddy URL).
2. Restart HA.

   ✓ Checkpoint: Developer Tools → States shows `sensor.sun_sign`,
   `sensor.moon_phase_astrolog`, `binary_sensor.mercury_retrograde`, etc.

3. Ideas: a Mushroom template card showing "☽ Waxing Gibbous in Scorpio ·
   Mercury Rx", or condition your evening lighting scene on moon phase.

## API reference

| Endpoint | Purpose |
|---|---|
| `GET /api/now?lat=&lon=` | Current positions, houses, aspects, moon |
| `GET /api/ha` | Flat JSON for HA REST sensors |
| `GET /api/charts` | List saved natal charts |
| `POST /api/charts` | Save: `{name, date, time, tz, lat, lon}` |
| `GET /api/charts/<name>` | One saved chart |
| `DELETE /api/charts/<name>` | Remove a chart |
| `GET /api/transits/<name>` | Current sky + aspects to that natal chart |

## Local development (no Docker)

```bash
cd backend
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
python3 app.py        # http://localhost:5000

```
## License

Copyright © 2026 Gabby Pike

This project is licensed under the AGPL-3.0 — see [LICENSE](LICENSE).
Astronomical calculations powered by the
[Swiss Ephemeris](https://www.astro.com/swisseph/) via
[pyswisseph](https://github.com/astrorigin/pyswisseph), used under the AGPL.
