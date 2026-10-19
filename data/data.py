import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

_DATASWORN_COMMIT = "c86923819213f1321170586c4543ceea70bc3d5c"
_DATASWORN_BASE = f"https://raw.githubusercontent.com/rsek/datasworn/{_DATASWORN_COMMIT}/datasworn"
_WORDMILL_BASE = "https://raw.githubusercontent.com/aradix85/wordmill-data/master"
_USER_AGENT = {"User-Agent": "Straightjacket-Data-Loader/1.0"}

SOURCES = {
    "classic": {
        "url": f"{_DATASWORN_BASE}/classic/classic.json",
        "file": "classic.json",
        "license": "CC-BY-4.0",
        "group": "datasworn",
    },
    "delve": {
        "url": f"{_DATASWORN_BASE}/delve/delve.json",
        "file": "delve.json",
        "license": "CC-BY-4.0",
        "group": "datasworn",
    },
    "starforged": {
        "url": f"{_DATASWORN_BASE}/starforged/starforged.json",
        "file": "starforged.json",
        "license": "CC-BY-4.0",
        "group": "datasworn",
    },
    "sundered_isles": {
        "url": f"{_DATASWORN_BASE}/sundered_isles/sundered_isles.json",
        "file": "sundered_isles.json",
        "license": "CC-BY-NC-SA-4.0",
        "group": "datasworn",
    },
    "mythic_gme_2e": {
        "url": f"{_WORDMILL_BASE}/mythic_gme_2e.json",
        "file": "mythic_gme_2e.json",
        "license": "CC-BY-NC-4.0",
        "group": "mythic",
    },
    "adventure_crafter": {
        "url": f"{_WORDMILL_BASE}/adventure_crafter.json",
        "file": "adventure_crafter.json",
        "license": "CC-BY-NC-4.0",
        "group": "mythic",
    },
}

_GROUP_LABELS = {
    "datasworn": "Datasworn (Ironsworn family)",
    "mythic": "Word Mill Games (Mythic family)",
}


def _fetch(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers=_USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data: bytes = resp.read()
    return data


def _download(url: str, dest: Path) -> bool:
    try:
        print(f"  Downloading {url[:80]}...")
        dest.write_bytes(_fetch(url, timeout=30))
        return True
    except (urllib.error.URLError, OSError) as e:
        print(f"  FAILED: {e}")
        return False


def main() -> None:
    force = "--force" in sys.argv

    print(f"Data directory: {DATA_DIR}")
    print()

    ok = 0
    skipped = 0
    failed = 0

    current_group = None
    for source_id, source in SOURCES.items():
        if source["group"] != current_group:
            current_group = source["group"]
            print(f"── {_GROUP_LABELS[current_group]} ──")

        dest = DATA_DIR / source["file"]
        if dest.exists() and not force:
            size_kb = dest.stat().st_size / 1024
            print(f"  {source_id}: already exists ({size_kb:.0f}K), skipping")
            skipped += 1
            continue

        print(f"  {source_id} ({source['license']}):")
        if _download(source["url"], dest):
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
