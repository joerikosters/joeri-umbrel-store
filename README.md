# Joeri Store

A [Community App Store](https://github.com/getumbrel/umbrel-community-app-store) for umbrelOS.

## Apps

- **[EVCC](joeri-store-evcc)** — open-source EV charge controller & solar
  charging optimizer. Runs in host networking mode (see its own notes below);
  reachable at `http://umbrel.local:7070`, not through the dashboard proxy.
- **[Homebridge A](joeri-store-homebridge-a)** / **[Homebridge B](joeri-store-homebridge-b)**
  — two independent clones of the official Homebridge app, for running two
  separate HomeKit bridges on the same Umbrel. Both host networking;
  Homebridge A at `http://umbrel.local:8581` (default), Homebridge B at
  `http://umbrel.local:8582` (moved via `HOMEBRIDGE_CONFIG_UI_PORT` to avoid
  colliding with A). See their umbrel-app.yml descriptions for an
  mDNS/avahi caveat when running two HomeKit bridges host-networked at once.

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
