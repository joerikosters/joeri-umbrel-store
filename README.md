# Joeri Store

A [Community App Store](https://github.com/getumbrel/umbrel-community-app-store) for umbrelOS.

## Apps

- **[EVCC](joeri-store-evcc)** — open-source EV charge controller & solar
  charging optimizer.

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
- The `app_proxy` service in each `docker-compose.yml` is what makes the app
  reachable through the Umbrel dashboard (and Tor); point its `APP_HOST` at
  `<app-id>_<compose-service-name>_1`.
