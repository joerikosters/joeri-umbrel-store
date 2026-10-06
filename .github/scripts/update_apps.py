#!/usr/bin/env python3
"""Keeps this store's apps in sync with their upstream source.

Two sync strategies:

- "dockerhub_tag": checks Docker Hub directly for a newer stable release
  tag of a pinned image, and bumps docker-compose.yml's image line plus
  umbrel-app.yml's version/releaseNotes to match. Used for apps that are
  this store's own thing (e.g. evcc), not a clone of an official app.

- "official_clone": re-clones an app from the official getumbrel/umbrel-apps
  store whenever its `version` changes, carrying over everything upstream
  (description, releaseNotes, permissions, volumes, etc.) but reapplying
  this store's own overrides (id, name, port, icon, gallery, a port-change
  environment var, and an extra description/releaseNotes note) on top. Used
  for joeri-store-homebridge-a/b, which are renamed clones of the official
  Homebridge app with just a different UI port.

Neither strategy uses image:latest + pull_policy:always — apps stay pinned
to a specific tag (and digest, where the app pins one), so Umbrel's own
"Update available" flow is what applies the change, not a silent re-pull on
container restart.
"""

import json
import os
import re
import textwrap
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UMBREL_APPS_RAW = "https://raw.githubusercontent.com/getumbrel/umbrel-apps/master"

APPS = [
    {
        "strategy": "dockerhub_tag",
        "dir": "joeri-store-evcc",
        "repo": "evcc/evcc",
        "tag_regex": r"^\d+\.\d+\.\d+$",
        "pin_digest": False,
        "version_template": "{tag}",
    },
    {
        "strategy": "official_clone",
        "dir": "joeri-store-homebridge-a",
        "upstream_app": "homebridge",
        "id": "joeri-store-homebridge-a",
        "name": "Homebridge A",
        "port": 8591,
        "other_name": "Homebridge B",
        "icon": "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/homebridge.png",
        "gallery": ["https://image.thum.io/get/width/1280/noanimate/https://homebridge.io"],
    },
    {
        "strategy": "official_clone",
        "dir": "joeri-store-homebridge-b",
        "upstream_app": "homebridge",
        "id": "joeri-store-homebridge-b",
        "name": "Homebridge B",
        "port": 8592,
        "other_name": "Homebridge A",
        "icon": "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/homebridge.png",
        "gallery": ["https://image.thum.io/get/width/1280/noanimate/https://homebridge.io"],
    },
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "joeri-store-update-bot"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "joeri-store-update-bot"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def wrap_note(note, indent="  "):
    return "\n".join(textwrap.wrap(note, width=77, initial_indent=indent, subsequent_indent=indent))


# ---------------------------------------------------------------------------
# Strategy: dockerhub_tag
# ---------------------------------------------------------------------------

def latest_tag(repo, tag_regex):
    pattern = re.compile(tag_regex)
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=100&ordering=last_updated"
    data = fetch_json(url)
    for result in data.get("results", []):
        if pattern.match(result["name"]):
            return result["name"]
    raise RuntimeError(f"No tag matching {tag_regex} found for {repo}")


def digest_for_tag(repo, tag):
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"
    data = fetch_json(url)
    digest = data.get("digest")
    if not digest:
        raise RuntimeError(f"No digest found for {repo}:{tag}")
    return digest


def current_image(compose_path, repo):
    text = compose_path.read_text()
    m = re.search(rf"image:\s*({re.escape(repo)}:\S+)", text)
    if not m:
        raise RuntimeError(f"Could not find image for {repo} in {compose_path}")
    return m.group(1)


def sync_dockerhub_tag(app):
    app_dir = ROOT / app["dir"]
    compose_path = app_dir / "docker-compose.yml"
    manifest_path = app_dir / "umbrel-app.yml"

    old_image = current_image(compose_path, app["repo"])
    tag = latest_tag(app["repo"], app["tag_regex"])

    if app["pin_digest"]:
        digest = digest_for_tag(app["repo"], tag)
        new_image = f"{app['repo']}:{tag}@{digest}"
    else:
        new_image = f"{app['repo']}:{tag}"

    if new_image == old_image:
        print(f"{app['dir']}: up to date ({old_image})")
        return None

    new_version = app["version_template"].format(tag=tag)
    note = (
        f"Automated update: bumped {app['repo']} to upstream release "
        f"`{tag}`, applied by this store's scheduled GitHub Action. "
        f"Check the project's own release notes before relying on new "
        f"behavior — this note is generated, not reviewed."
    )

    compose_text = compose_path.read_text()
    if old_image not in compose_text:
        raise RuntimeError(f"Could not find image {old_image!r} in {compose_path}")
    compose_path.write_text(compose_text.replace(old_image, new_image, 1))

    manifest_text = manifest_path.read_text()
    manifest_text, n = re.subn(
        r'^version:\s*".*"$', f'version: "{new_version}"', manifest_text, count=1, flags=re.MULTILINE
    )
    if n != 1:
        raise RuntimeError(f"Could not update version in {manifest_path}")
    manifest_text, n = re.subn(
        r"^releaseNotes: >-\n(?:[ \t]+.*\n|\n)*",
        f"releaseNotes: >-\n{wrap_note(note)}\n",
        manifest_text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise RuntimeError(f"Could not update releaseNotes in {manifest_path}")
    manifest_path.write_text(manifest_text)

    return f"{app['dir']}: {old_image} -> {new_image}"


# ---------------------------------------------------------------------------
# Strategy: official_clone
# ---------------------------------------------------------------------------

def local_version(manifest_path):
    if not manifest_path.exists():
        return None
    m = re.search(r'^version:\s*"(.*)"$', manifest_path.read_text(), flags=re.MULTILINE)
    return m.group(1) if m else None


def sync_official_clone(app):
    app_dir = ROOT / app["dir"]
    manifest_path = app_dir / "umbrel-app.yml"
    compose_path = app_dir / "docker-compose.yml"

    upstream_manifest = fetch_text(f"{UMBREL_APPS_RAW}/{app['upstream_app']}/umbrel-app.yml")
    upstream_compose = fetch_text(f"{UMBREL_APPS_RAW}/{app['upstream_app']}/docker-compose.yml")

    m = re.search(r'^version:\s*"(.*)"$', upstream_manifest, flags=re.MULTILINE)
    if not m:
        raise RuntimeError(f"Could not find version in upstream {app['upstream_app']}/umbrel-app.yml")
    upstream_version = m.group(1)

    if local_version(manifest_path) == upstream_version:
        print(f"{app['dir']}: up to date (upstream {upstream_version})")
        return None

    text = upstream_manifest

    text, n = re.subn(r"^id:.*$", f"id: {app['id']}", text, count=1, flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError(f"Could not set id in upstream manifest for {app['dir']}")

    text, n = re.subn(r"^name:.*$", f"name: {app['name']}", text, count=1, flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError(f"Could not set name in upstream manifest for {app['dir']}")

    text, n = re.subn(r"^port:.*$", f"port: {app['port']}", text, count=1, flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError(f"Could not set port in upstream manifest for {app['dir']}")

    # Upstream has no icon field — insert ours after `website:`.
    text, n = re.subn(
        r"^(website:.*)$", rf"\1\nicon: {app['icon']}", text, count=1, flags=re.MULTILINE
    )
    if n != 1:
        raise RuntimeError(f"Could not insert icon in upstream manifest for {app['dir']}")

    # Upstream's gallery references local image files (1.jpg, ...) served by
    # Umbrel's own CDN under the *official* app id — meaningless under our
    # app id, so replace wholesale with our own external screenshot.
    gallery_block = "gallery:\n" + "\n".join(f"  - {url}" for url in app["gallery"]) + "\n"
    text, n = re.subn(
        r"^gallery:\n(?:[ \t]+-.*\n)+", gallery_block, text, count=1, flags=re.MULTILINE
    )
    if n != 1:
        raise RuntimeError(f"Could not replace gallery in upstream manifest for {app['dir']}")

    # Append our own paragraphs to the end of the description block.
    port_note = wrap_note(
        f"This is \"{app['name']}\", one of two independent Homebridge "
        f"instances in the Joeri Store (the other is \"{app['other_name']}\"), "
        f"for running two separate HomeKit bridges on the same Umbrel. Open "
        f"it directly at http://umbrel.local:{app['port']} (moved off "
        f"Homebridge's default UI port 8581, via HOMEBRIDGE_CONFIG_UI_PORT, "
        f"so it never collides with the other instance or a stock "
        f"Homebridge install on the same host network).",
        indent="  ",
    )
    caveat_note = wrap_note(
        "Known caveat: each instance runs its own bundled Avahi (mDNS) "
        "daemon inside its container, alongside umbrelOS's own avahi-daemon "
        "on the host — all competing for UDP port 5353 in the shared host "
        "network namespace. With two Homebridge instances plus umbrelOS "
        "itself, HomeKit discovery for one or both bridges may be flaky. If "
        "that happens, see the docker-homebridge docs for disabling the "
        "bundled Avahi (ENABLE_AVAHI=0) and mounting the host's D-Bus/Avahi "
        "socket instead — not pre-configured here since it depends on "
        "umbrelOS's avahi-daemon exposing that socket.",
        indent="  ",
    )
    text, n = re.subn(
        r"(^description: >-\n(?:[ \t]*.*\n|\n)*?)(?=^\S)",
        rf"\1\n\n{port_note}\n\n\n{caveat_note}\n\n\n",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise RuntimeError(f"Could not extend description in upstream manifest for {app['dir']}")

    text, n = re.subn(r"^submitter:.*$", "submitter: Joeri Store", text, count=1, flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError(f"Could not set submitter in upstream manifest for {app['dir']}")
    text, n = re.subn(r'^submission:.*$', 'submission: ""', text, count=1, flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError(f"Could not set submission in upstream manifest for {app['dir']}")

    sync_note = wrap_note(
        f"Synced automatically from the official Homebridge app in Umbrel's "
        f"own app store (upstream version `{upstream_version}`), by this "
        f"store's GitHub Action. Port, icon and gallery overrides from this "
        f"store are reapplied on top of upstream's definition — see this "
        f"app's description for details. This note is generated, not "
        f"reviewed; check upstream's own release notes below.",
        indent="  ",
    )
    text, n = re.subn(
        r"^releaseNotes: >-\n(?:[ \t]*.*\n|\n)*(?=^submitter:)",
        f"releaseNotes: >-\n{sync_note}\n\n\n  Upstream release notes:\n\n\n",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise RuntimeError(f"Could not rewrite releaseNotes in upstream manifest for {app['dir']}")

    # Re-append the upstream releaseNotes body (captured before rewriting)
    # as a quoted continuation, so both notes exist in one block scalar.
    m = re.search(r"^releaseNotes: >-\n((?:[ \t]*.*\n|\n)*)(?=^submitter:)", upstream_manifest, flags=re.MULTILINE)
    upstream_release_notes_body = m.group(1) if m else ""
    text = text.replace(
        f"releaseNotes: >-\n{sync_note}\n\n\n  Upstream release notes:\n\n\n",
        f"releaseNotes: >-\n{sync_note}\n\n\n  Upstream release notes:\n\n\n{upstream_release_notes_body}",
        1,
    )

    manifest_path.write_text(text)

    # docker-compose.yml: carry upstream verbatim, inject our UI-port env var.
    compose_text = upstream_compose
    env_block = (
        "    environment:\n"
        "      # Moves the Homebridge UI off the image's default port 8581,\n"
        "      # so this instance never collides with the other Homebridge\n"
        "      # clone or a stock Homebridge install on the same host\n"
        "      # network.\n"
        f"      - HOMEBRIDGE_CONFIG_UI_PORT={app['port']}\n"
    )
    if "environment:" in compose_text:
        raise RuntimeError(
            f"Upstream docker-compose.yml for {app['upstream_app']} now has its own "
            f"environment: block — update sync_official_clone to merge instead of "
            f"inserting a new one."
        )
    compose_text, n = re.subn(
        r"^(\s*image:.*\n)", rf"\1{env_block}", compose_text, count=1, flags=re.MULTILINE
    )
    if n != 1:
        raise RuntimeError(f"Could not inject environment block in upstream compose for {app['dir']}")

    compose_text, n = re.subn(
        r"^\s*# available at port \d+\s*$",
        f"    # available at port {app['port']} (see environment above)",
        compose_text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise RuntimeError(f"Could not update port comment in upstream compose for {app['dir']}")

    compose_path.write_text(compose_text)

    return f"{app['dir']}: synced from official homebridge {upstream_version}"


# ---------------------------------------------------------------------------

def main():
    changed = []
    for app in APPS:
        if app["strategy"] == "dockerhub_tag":
            result = sync_dockerhub_tag(app)
        elif app["strategy"] == "official_clone":
            result = sync_official_clone(app)
        else:
            raise RuntimeError(f"Unknown strategy {app['strategy']!r} for {app['dir']}")
        if result:
            changed.append(result)
            print(result)

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if changed:
        message = "Automated dependency update\n\n" + "\n".join(f"- {c}" for c in changed)
        Path("/tmp/commit_message.txt").write_text(message)
        if gh_output:
            with open(gh_output, "a") as f:
                f.write("changed=true\n")
    else:
        print("No updates found.")
        if gh_output:
            with open(gh_output, "a") as f:
                f.write("changed=false\n")


if __name__ == "__main__":
    main()
