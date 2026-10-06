#!/usr/bin/env python3
"""Checks each app's upstream Docker image for a newer stable release tag
and, if found, bumps docker-compose.yml's image line and umbrel-app.yml's
version/releaseNotes to match. Leaves committing to the calling workflow.

This intentionally does NOT use image:latest + pull_policy:always — apps
stay pinned to a specific tag (and digest, where the app pins one), so
Umbrel's own "Update available" flow is what applies the change, not a
silent re-pull on container restart.
"""

import json
import os
import re
import textwrap
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

APPS = [
    {
        "dir": "joeri-store-evcc",
        "repo": "evcc/evcc",
        "tag_regex": r"^\d+\.\d+\.\d+$",
        "pin_digest": False,
        "version_template": "{tag}",
    },
    {
        "dir": "joeri-store-homebridge-a",
        "repo": "homebridge/homebridge",
        "tag_regex": r"^\d{4}-\d{2}-\d{2}$",
        "pin_digest": True,
        "version_template": "2.4.0-{tag}",
    },
    {
        "dir": "joeri-store-homebridge-b",
        "repo": "homebridge/homebridge",
        "tag_regex": r"^\d{4}-\d{2}-\d{2}$",
        "pin_digest": True,
        "version_template": "2.4.0-{tag}",
    },
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "joeri-store-update-bot"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


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


def update_compose(path, old_image, new_image):
    text = path.read_text()
    if old_image not in text:
        raise RuntimeError(f"Could not find image {old_image!r} in {path}")
    path.write_text(text.replace(old_image, new_image, 1))


def update_manifest(path, new_version, note):
    text = path.read_text()

    text, n = re.subn(
        r'^version:\s*".*"$',
        f'version: "{new_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise RuntimeError(f"Could not update version in {path}")

    wrapped_note = "\n".join(
        textwrap.wrap(note, width=77, initial_indent="  ", subsequent_indent="  ")
    )
    text, n = re.subn(
        r"^releaseNotes: >-\n(?:[ \t]+.*\n|\n)*",
        f"releaseNotes: >-\n{wrapped_note}\n",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise RuntimeError(f"Could not update releaseNotes in {path}")

    path.write_text(text)


def main():
    changed = []
    for app in APPS:
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
            continue

        new_version = app["version_template"].format(tag=tag)
        note = (
            f"Automated update: bumped {app['repo']} to upstream release "
            f"`{tag}`, applied by this store's scheduled GitHub Action. "
            f"Check the project's own release notes before relying on new "
            f"behavior — this note is generated, not reviewed."
        )

        update_compose(compose_path, old_image, new_image)
        update_manifest(manifest_path, new_version, note)
        changed.append(f"{app['dir']}: {old_image} -> {new_image}")
        print(f"{app['dir']}: {old_image} -> {new_image}")

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
