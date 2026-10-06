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
5. To have new upstream releases bumped automatically instead of by hand,
   add the app to `APPS` in `.github/scripts/update_apps.py` (see below).

## Automated update checker

A scheduled GitHub Action (`.github/workflows/update-apps.yml`, daily at
06:00 UTC, or run manually via the Actions tab) keeps each app listed in
`.github/scripts/update_apps.py` in sync with its upstream source, using
one of two strategies per app:

- **`dockerhub_tag`** (used by `joeri-store-evcc`): checks Docker Hub
  directly for a newer stable release tag of the pinned image, and bumps
  `image:` in `docker-compose.yml` plus `version`/`releaseNotes` in
  `umbrel-app.yml` to match.
- **`official_clone`** (used by `joeri-store-homebridge-a`/`-b`): whenever
  the official Homebridge app's `version` changes in
  [getumbrel/umbrel-apps](https://github.com/getumbrel/umbrel-apps), re-clones
  its `umbrel-app.yml`/`docker-compose.yml` wholesale — carrying over
  upstream's description, releaseNotes, permissions, volumes, etc. — then
  reapplies this store's own overrides on top: `id`, `name`, `port`, `icon`
  and `gallery` (upstream's gallery references files that only exist under
  the official app id), a `HOMEBRIDGE_CONFIG_UI_PORT` environment var for
  the port change, and an extra description/releaseNotes paragraph about
  running two instances. Use this strategy for any future app that's meant
  to track an official Umbrel app's updates under a renamed/customized
  clone.

Either way, apps stay pinned to a specific tag (and digest, for apps that
pin one) — this does **not** use `image:latest` + `pull_policy: always`.
The bot keeps the pin current automatically; Umbrel's own "Update
available" → click flow still applies the actual change, so you keep
version pinning, rollback, and a visible update step. The releaseNotes text
the bot writes (or re-wraps, for `official_clone`) is generated/relayed,
not reviewed — treat it as a pointer to go check the project's own release
notes, not a substitute for them.

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
