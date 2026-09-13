#!/usr/bin/env python3
"""Validate every document in this repository the way the launcher will.

The launcher rejects a malformed document and shows the player an error, which is
the right behaviour at runtime and a terrible way to find out. This is the same set
of rules, run in CI, so a hand-edited `news.json` fails a pull request instead of a
player's launcher.

It deliberately duplicates `LauncherValidator.gd` rather than sharing code with it:
this repository holds no Godot project, and a check that needed the engine installed
would not run.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCHEMA_CATALOG = "kyvora.catalog/1"
SCHEMA_GAME = "kyvora.game/1"
SCHEMA_CHANNEL = "kyvora.channel/1"
SCHEMA_MANIFEST = "kyvora.manifest/1"
SCHEMA_NEWS = "kyvora.news/1"

NEWS_KINDS = {"news", "patch_notes", "event", "hotfix"}
PLATFORMS = {"windows", "linux", "macos"}
PRESERVED = {"saves", "logs", ".staging"}
STATE_FILE = "installed.json"

SLUG = re.compile(r"^[a-z0-9_-]+$")
VERSION = re.compile(r"^v?\d+(\.\d+)*(-[0-9A-Za-z.-]+)?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

OWNER_PLACEHOLDER = "KYVORA_OWNER"


class Problems:
    def __init__(self) -> None:
        self.entries: list[str] = []

    def add(self, where: str, message: str) -> None:
        self.entries.append(f"{where}: {message}")

    def ok(self) -> bool:
        return not self.entries


def require(problems: Problems, doc: dict, where: str, field: str, check, description: str) -> None:
    if field not in doc or doc[field] is None:
        problems.add(f"{where}.{field}", "required field is missing")
        return
    if not check(doc[field]):
        problems.add(f"{where}.{field}", f"{doc[field]!r} {description}")


def optional(problems: Problems, doc: dict, where: str, field: str, check, description: str) -> None:
    if field in doc and doc[field] is not None and not check(doc[field]):
        problems.add(f"{where}.{field}", f"{doc[field]!r} {description}")


def is_https(value) -> bool:
    # Every byte a manifest names is executed on a player's machine, so plain http
    # is refused rather than warned about. `res://` is art bundled in the launcher.
    return isinstance(value, str) and (value.startswith("https://") or value.startswith("res://"))


def is_slug(value) -> bool:
    return isinstance(value, str) and bool(SLUG.match(value))


def is_version(value) -> bool:
    return isinstance(value, str) and bool(VERSION.match(value))


def is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def check_url_map(problems: Problems, doc: dict, where: str, field: str, platform_keys: bool) -> None:
    value = doc.get(field)
    if not isinstance(value, dict) or not value:
        problems.add(f"{where}.{field}", "must be a non-empty object")
        return
    for key, url in value.items():
        if platform_keys and key not in PLATFORMS:
            problems.add(f"{where}.{field}.{key}", "is not a supported platform")
        if not is_https(url):
            problems.add(f"{where}.{field}.{key}", f"{url!r} must be an https:// URL")


def check_relative_path(problems: Problems, path, where: str) -> None:
    if not isinstance(path, str) or not path.strip():
        problems.add(where, "path is empty")
        return
    if "\\" in path:
        problems.add(where, f"{path!r} must use '/' separators")
    if path.startswith("/") or ":" in path:
        problems.add(where, f"{path!r} must be relative to the install directory")
    parts = path.split("/")
    if any(part in (".", "..") for part in parts):
        problems.add(where, f"{path!r} must not contain '.' or '..' segments")
        return
    if parts[0] in PRESERVED or path == STATE_FILE:
        problems.add(where, f"{path!r} is inside something the launcher never overwrites")


def check_game_entry(problems: Problems, entry: dict, where: str) -> None:
    optional(problems, entry, where, "schema", lambda v: v == SCHEMA_GAME, f"must be {SCHEMA_GAME}")
    require(problems, entry, where, "id", is_slug, "must be a lowercase slug")
    require(problems, entry, where, "title", is_text, "must be a non-empty string")
    require(problems, entry, where, "install_dir_name", is_slug, "must be a lowercase slug")
    require(problems, entry, where, "default_channel", is_slug, "must be a lowercase slug")
    check_url_map(problems, entry, where, "channels", platform_keys=False)
    optional(problems, entry, where, "news", is_https, "must be an https:// URL")
    executables = entry.get("executables")
    if not isinstance(executables, dict) or not executables:
        problems.add(f"{where}.executables", "must name at least one platform")
    else:
        for platform, name in executables.items():
            if platform not in PLATFORMS:
                problems.add(f"{where}.executables.{platform}", "is not a supported platform")
            check_relative_path(problems, name, f"{where}.executables.{platform}")
    default_channel = entry.get("default_channel")
    channels = entry.get("channels")
    if isinstance(channels, dict) and default_channel not in channels:
        problems.add(f"{where}.default_channel", f"{default_channel!r} is not one of the channels")


def check_catalog(problems: Problems, doc: dict, where: str) -> None:
    require(problems, doc, where, "schema", lambda v: v == SCHEMA_CATALOG, f"must be {SCHEMA_CATALOG}")
    games = doc.get("games")
    if not isinstance(games, list) or not games:
        problems.add(f"{where}.games", "must be a non-empty array")
        return
    seen = set()
    for index, entry in enumerate(games):
        entry_where = f"{where}.games[{index}]"
        if not isinstance(entry, dict):
            problems.add(entry_where, "must be an object")
            continue
        check_game_entry(problems, entry, entry_where)
        game_id = entry.get("id")
        if game_id in seen:
            problems.add(entry_where, f"{game_id!r} appears twice")
        seen.add(game_id)


def check_channel(problems: Problems, doc: dict, where: str) -> None:
    require(problems, doc, where, "schema", lambda v: v == SCHEMA_CHANNEL, f"must be {SCHEMA_CHANNEL}")
    require(problems, doc, where, "version", is_version, "is not a dotted version")
    optional(problems, doc, where, "game_id", is_slug, "must be a lowercase slug")
    optional(problems, doc, where, "channel", is_slug, "must be a lowercase slug")
    optional(problems, doc, where, "notes_url", is_https, "must be an https:// URL")
    optional(problems, doc, where, "minimum_launcher_version", is_version, "is not a dotted version")
    check_url_map(problems, doc, where, "manifests", platform_keys=True)


def check_manifest(problems: Problems, doc: dict, where: str) -> None:
    require(problems, doc, where, "schema", lambda v: v == SCHEMA_MANIFEST, f"must be {SCHEMA_MANIFEST}")
    require(problems, doc, where, "game_id", is_slug, "must be a lowercase slug")
    require(problems, doc, where, "version", is_version, "is not a dotted version")
    require(problems, doc, where, "platform", lambda v: v in PLATFORMS, "is not a supported platform")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        problems.add(f"{where}.entries", "must be a non-empty array")
        return
    seen = set()
    for index, entry in enumerate(entries):
        entry_where = f"{where}.entries[{index}]"
        if not isinstance(entry, dict):
            problems.add(entry_where, "must be an object")
            continue
        check_relative_path(problems, entry.get("path"), f"{entry_where}.path")
        require(problems, entry, entry_where, "size", is_whole, "must be a whole number of bytes")
        require(problems, entry, entry_where, "sha256", lambda v: isinstance(v, str) and bool(SHA256.match(v)),
                "is not a 64-character lowercase hex digest")
        require(problems, entry, entry_where, "url", is_https, "must be an https:// URL")
        path = entry.get("path")
        if path in seen:
            problems.add(entry_where, f"{path!r} appears twice")
        seen.add(path)


def check_news(problems: Problems, doc: dict, where: str) -> None:
    require(problems, doc, where, "schema", lambda v: v == SCHEMA_NEWS, f"must be {SCHEMA_NEWS}")
    entries = doc.get("entries")
    if not isinstance(entries, list):
        problems.add(f"{where}.entries", "must be an array")
        return
    seen = set()
    for index, entry in enumerate(entries):
        entry_where = f"{where}.entries[{index}]"
        if not isinstance(entry, dict):
            problems.add(entry_where, "must be an object")
            continue
        require(problems, entry, entry_where, "id", is_text, "must be a non-empty string")
        require(problems, entry, entry_where, "title", is_text, "must be a non-empty string")
        require(problems, entry, entry_where, "date", lambda v: isinstance(v, str) and bool(DATE.match(v)),
                "is not an ISO date (YYYY-MM-DD)")
        require(problems, entry, entry_where, "kind", lambda v: v in NEWS_KINDS,
                f"is not one of {sorted(NEWS_KINDS)}")
        optional(problems, entry, entry_where, "version", is_version, "is not a dotted version")
        for field in ("body_url", "image", "url"):
            optional(problems, entry, entry_where, field, is_https, "must be an https:// URL")
        entry_id = entry.get("id")
        if entry_id in seen:
            problems.add(entry_where, f"{entry_id!r} appears twice")
        seen.add(entry_id)

        # A body that lives in this repository is checked for existence: a dead
        # link in the feed is a note that opens to nothing.
        body_url = entry.get("body_url")
        if isinstance(body_url, str) and "/kyvora-releases/main/" in body_url:
            relative = body_url.split("/kyvora-releases/main/", 1)[1]
            if not (ROOT / relative).exists():
                problems.add(f"{entry_where}.body_url", f"{relative} is not in this repository")


def documents() -> list[tuple[Path, object]]:
    found: list[tuple[Path, object]] = []
    catalog = ROOT / "catalog.json"
    if catalog.exists():
        found.append((catalog, check_catalog))
    for path in sorted(ROOT.glob("**/channels/*.json")):
        found.append((path, check_channel))
    for path in sorted(ROOT.glob("games/*/news.json")):
        found.append((path, check_news))
    # Manifests normally live as release assets, but a copy kept here for
    # inspection should still be correct.
    for path in sorted(ROOT.glob("**/manifest-*.json")):
        found.append((path, check_manifest))
    return found


def main() -> int:
    problems = Problems()
    found = documents()
    if not found:
        print("no documents found - is this the right directory?")
        return 1
    placeholders = 0
    for path, check in found:
        relative = path.relative_to(ROOT).as_posix()
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            problems.add(relative, f"not valid JSON ({error})")
            continue
        if not isinstance(doc, dict):
            problems.add(relative, "must be a JSON object")
            continue
        check(problems, doc, relative)
        if OWNER_PLACEHOLDER in path.read_text():
            placeholders += 1

    for entry in problems.entries:
        print(f"FAIL {entry}")
    print(f"checked {len(found)} documents, {len(problems.entries)} problems")
    if placeholders:
        # Not a failure. The repository ships with the placeholder in place, and
        # the first `publish.py` run replaces it.
        print(f"note: {placeholders} documents still name {OWNER_PLACEHOLDER}")
    return 0 if problems.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
