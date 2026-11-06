import logging
import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

_CONSOLE = logging.getLogger("straightjacket.data")
_CONSOLE_HANDLER = logging.StreamHandler(sys.stdout)
_CONSOLE_HANDLER.setFormatter(logging.Formatter("%(message)s"))
_CONSOLE.addHandler(_CONSOLE_HANDLER)
_CONSOLE.setLevel(logging.INFO)
_CONSOLE.propagate = False


def _say(text: str = "") -> None:
    _CONSOLE.info(text)


_DATASWORN_COMMIT = "c86923819213f1321170586c4543ceea70bc3d5c"
_DATASWORN_PATH = f"rsek/datasworn/{_DATASWORN_COMMIT}/datasworn"
_WORDMILL_PATH = "aradix85/wordmill-data/master"
_USER_AGENT = {"User-Agent": "Straightjacket-Data-Loader/1.0"}
_HTTPS_ONLY = urllib.request.OpenerDirector()
for _handler in (
    urllib.request.ProxyHandler(),
    urllib.request.HTTPSHandler(),
    urllib.request.HTTPRedirectHandler(),
    urllib.request.HTTPDefaultErrorHandler(),
    urllib.request.HTTPErrorProcessor(),
    urllib.request.UnknownHandler(),
):
    _HTTPS_ONLY.add_handler(_handler)

SOURCES = {
    "classic": {
        "path": f"{_DATASWORN_PATH}/classic/classic.json",
        "file": "classic.json",
        "license": "CC-BY-4.0",
        "group": "datasworn",
    },
    "delve": {
        "path": f"{_DATASWORN_PATH}/delve/delve.json",
        "file": "delve.json",
        "license": "CC-BY-4.0",
        "group": "datasworn",
    },
    "starforged": {
        "path": f"{_DATASWORN_PATH}/starforged/starforged.json",
        "file": "starforged.json",
        "license": "CC-BY-4.0",
        "group": "datasworn",
    },
    "sundered_isles": {
        "path": f"{_DATASWORN_PATH}/sundered_isles/sundered_isles.json",
        "file": "sundered_isles.json",
        "license": "CC-BY-NC-SA-4.0",
        "group": "datasworn",
    },
    "mythic_gme_2e": {
        "path": f"{_WORDMILL_PATH}/mythic_gme_2e.json",
        "file": "mythic_gme_2e.json",
        "license": "CC-BY-NC-4.0",
        "group": "mythic",
    },
    "adventure_crafter": {
        "path": f"{_WORDMILL_PATH}/adventure_crafter.json",
        "file": "adventure_crafter.json",
        "license": "CC-BY-NC-4.0",
        "group": "mythic",
    },
}

_GROUP_LABELS = {
    "datasworn": "Datasworn (Ironsworn family)",
    "mythic": "Word Mill Games (Mythic family)",
}


def _fetch(path: str, timeout: int) -> bytes:
    request = urllib.request.Request(f"https://raw.githubusercontent.com/{path}", headers=_USER_AGENT)
    with _HTTPS_ONLY.open(request, timeout=timeout) as response:
        data: bytes = response.read()
    return data


def _download(path: str, dest: Path) -> bool:
    try:
        _say(f"  Downloading {path[:80]}...")
        dest.write_bytes(_fetch(path, timeout=30))
    except OSError as e:
        _say(f"  FAILED: {e}")
        return False
    return True


def main() -> None:
    force = "--force" in sys.argv

    _say(f"Data directory: {DATA_DIR}")
    _say()

    ok = 0
    skipped = 0
    failed = 0

    current_group = None
    for source_id, source in SOURCES.items():
        if source["group"] != current_group:
            current_group = source["group"]
            _say(f"── {_GROUP_LABELS[current_group]} ──")

        dest = DATA_DIR / source["file"]
        if dest.exists() and not force:
            size_kb = dest.stat().st_size / 1024
            _say(f"  {source_id}: already exists ({size_kb:.0f}K), skipping")
            skipped += 1
            continue

        _say(f"  {source_id} ({source['license']}):")
        if _download(source["path"], dest):
            size_kb = dest.stat().st_size / 1024
            _say(f"  OK ({size_kb:.0f}K)")
            ok += 1
        else:
            failed += 1

    _say()
    _say(f"Done: {ok} downloaded, {skipped} skipped, {failed} failed")
    if failed:
        _say("Re-run to retry failed downloads.")
        sys.exit(1)


if __name__ == "__main__":
    main()
