# Joeri Store

A [Community App Store](https://github.com/getumbrel/umbrel-community-app-store) for umbrelOS.

## Apps

- **[EVCC](joeri-store-evcc)** — open-source EV charge controller & solar
  charging optimizer. Runs in host networking mode (see its own notes below);
  reachable at `http://umbrel.local:7070`, not through the dashboard proxy.
- **[Homebridge A](joeri-store-homebridge-a)** / **[Homebridge B](joeri-store-homebridge-b)**
  — two independent clones of the official Homebridge app, for running two
  separate HomeKit bridges on the same Umbrel. Both host networking;
  Homebridge A at `http://umbrel.local:8591`, Homebridge B at
  `http://umbrel.local:8592` (both moved off Homebridge's default UI port
  8581 via `HOMEBRIDGE_CONFIG_UI_PORT`, so neither collides with the other
  or with a stock Homebridge install). See their umbrel-app.yml
  descriptions for an mDNS/avahi caveat when running two HomeKit bridges
  host-networked at once.

## Using this store on umbrelOS

1. Push this repo to a public GitHub repository.
2. On your Umbrel, go to **App Store → ⋯ (top right) → Community App Stores**.
3. Paste the repo's URL and add it.
4. The "Joeri Store" will show up as a new tab in the App Store.

## Adding another app

1. Create a new folder named `joeri-store-<app-id>`.
2. Add `umbrel-app.yml` (app metadata) and `docker-compose.yml` (the app's
   Docker services) inside it — copy `joeri-store-evcc` as a starting point.
3. Bump `version` in `umbrel-app.yml` whenever you update the app, and add a
   line to `releaseNotes`.
4. Commit and push. Umbrel checks the store's git repo for updates.

## Image tagging: `latest` + `pull_policy: always`

Every app in this store pins its image to the `latest` tag with
`pull_policy: always` in `docker-compose.yml`, instead of a pinned
version/digest. This means Docker re-pulls the newest image on every
(re)start, so apps track upstream releases automatically — no more clicking
"Update" in Umbrel for routine upstream releases.

Trade-off, deliberately accepted: no version pinning, no rollback, and no
per-release release notes for the upstream project itself — a bad upstream
release (including a breaking major version bump) can change an app's
behavior with no warning, on any restart (including an Umbrel reboot).
`version`/`releaseNotes` in `umbrel-app.yml` are still bumped for changes
made *in this store* (port changes, compose fixes, etc.), just not for every
upstream release anymore.

## Notes

- Every app id in this store must be prefixed with `joeri-store-`, matching
  the `id` in `umbrel-app-store.yml`.
- `${APP_DATA_DIR}` and `${APP_PORT}` are supplied by umbrelOS at runtime —
  don't set them yourself.
- Most apps should include an `app_proxy` service in `docker-compose.yml` —
  that's what makes them reachable through the Umbrel dashboard (and Tor);
  point its `APP_HOST` at `<app-id>_<compose-service-name>_1`. Apps that need
  raw LAN access (multicast/broadcast discovery, arbitrary inbound ports) use
  `network_mode: host` instead and skip `app_proxy` entirely — see
  `joeri-store-evcc` for an example. Host-networked apps are reached directly
  at `http://umbrel.local:<port>`, with no Tor/.onion or auto-HTTPS.
