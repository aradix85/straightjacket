#!/usr/bin/env python3
"""Download Datasworn JSON data files.

Run once to populate the data/ directory. Safe to re-run — skips
existing files unless --force is passed.

Sources:
  classic.json, delve.json, starforged.json — rsek/datasworn GitHub repo
  sundered_isles.json — @datasworn/sundered-isles npm package

Licensing:
  Ironsworn Classic, Delve, Starforged: CC-BY-4.0
  Sundered Isles: CC-BY-NC-SA-4.0
  See https://github.com/rsek/datasworn for full license details.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

# GitHub raw URLs for compiled JSON (main branch, datasworn/ directory)
_GITHUB_BASE = "https://raw.githubusercontent.com/rsek/datasworn/main/datasworn"

# npm registry URL for Sundered Isles tarball
_NPM_REGISTRY = "https://registry.npmjs.org/@datasworn/sundered-isles"

SOURCES = {
    "classic": {
        "url": f"{_GITHUB_BASE}/classic/classic.json",
        "file": "classic.json",
        "license": "CC-BY-4.0",
    },
    "delve": {
        "url": f"{_GITHUB_BASE}/delve/delve.json",
        "file": "delve.json",
        "license": "CC-BY-4.0",
    },
    "starforged": {
        "url": f"{_GITHUB_BASE}/starforged/starforged.json",
        "file": "starforged.json",
        "license": "CC-BY-4.0",
    },
    "sundered_isles": {
        "url": "npm",  # special handling
        "file": "sundered_isles.json",
        "license": "CC-BY-NC-SA-4.0",
    },
}


def _download(url: str, dest: Path) -> bool:
    """Download a URL to a local file. Returns True on success."""
    try:
        print(f"  Downloading {url[:80]}...")
        req = urllib.request.Request(url, headers={"User-Agent": "Straightjacket-Datasworn-Loader/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return True
    except (urllib.error.URLError, OSError) as e:
        print(f"  FAILED: {e}")
        return False


def _download_sundered_isles(dest: Path) -> bool:
    """Download Sundered Isles JSON from npm registry.

    The npm tarball contains package/json/sundered_isles.json.
    We fetch the registry metadata, get the tarball URL, download it,
    and extract just the JSON file.
    """
    import io
    import tarfile

    try:
        # Get tarball URL from npm registry
        print("  Fetching npm registry metadata...")
        req = urllib.request.Request(_NPM_REGISTRY, headers={"User-Agent": "Straightjacket-Datasworn-Loader/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            meta = json.loads(resp.read())

        latest = meta.get("dist-tags", {}).get("latest", "")
        if not latest:
            print("  FAILED: no latest version in npm registry")
            return False

        tarball_url = meta["versions"][latest]["dist"]["tarball"]
        print(f"  Downloading {tarball_url}...")

        req = urllib.request.Request(tarball_url, headers={"User-Agent": "Straightjacket-Datasworn-Loader/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            tarball_bytes = resp.read()

        # Extract the JSON from the tarball
        with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tar:
            member = tar.getmember("package/json/sundered_isles.json")
            f = tar.extractfile(member)
            if f is None:
                print("  FAILED: could not extract JSON from tarball")
                return False
            dest.write_bytes(f.read())
        return True

    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def main():
    force = "--force" in sys.argv

    print(f"Datasworn data directory: {DATA_DIR}")
    print()

    ok = 0
    skipped = 0
    failed = 0

    for setting_id, source in SOURCES.items():
        dest = DATA_DIR / source["file"]
        if dest.exists() and not force:
            size_kb = dest.stat().st_size / 1024
            print(f"  {setting_id}: already exists ({size_kb:.0f}K), skipping")
            skipped += 1
            continue

        print(f"  {setting_id} ({source['license']}):")
        if source["url"] == "npm":
            success = _download_sundered_isles(dest)
        else:
            success = _download(source["url"], dest)

        if success:
            size_kb = dest.stat().st_size / 1024
            print(f"  OK ({size_kb:.0f}K)")
            ok += 1
        else:
            failed += 1

    print()
    print(f"Done: {ok} downloaded, {skipped} skipped, {failed} failed")
    if failed:
        print("Re-run to retry failed downloads.")
        sys.exit(1)


if __name__ == "__main__":
    main()
