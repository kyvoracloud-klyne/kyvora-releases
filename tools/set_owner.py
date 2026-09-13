#!/usr/bin/env python3
"""Replace the KYVORA_OWNER placeholder with a real GitHub account.

    python3 tools/set_owner.py yourname --launcher ../KyvoraLauncher

Every URL a player's launcher fetches names the account this repository lives
under, and those URLs are spread across two repositories: the documents here and
the catalog bundled into the launcher build. They have to agree — a launcher whose
bundled catalog points at the wrong account shows a game that can never install —
so this does both at once rather than leaving the second to be remembered.

The placeholder exists rather than a hardcoded name because this is public and
forkable: someone hosting their own games needs one command, not a search.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RELEASES_ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "KYVORA_OWNER"

# Only inside a URL, which in practice means only where a `/` comes first.
#
# That one condition is what makes this safe to run over its own source tree. The
# placeholder is also a constant in `validate_documents.py` and in the launcher's
# `HostConfig.gd`, both of which exist to *detect* it, and it is quoted in the two
# READMEs that explain this step. Substituting those would leave a repository that
# looks configured while the check that says otherwise has been rewritten to agree.
IN_URL = re.compile(r"(?<=/)" + PLACEHOLDER)

# Text only. A binary that happened to contain the placeholder bytes is not a URL,
# and rewriting one would corrupt it.
SUFFIXES = {".json", ".md", ".gd", ".yml", ".yaml", ".cfg", ".txt", ".py"}
SKIP_DIRS = {".git", ".godot", "build"}


def candidates(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        found.append(path)
    return found


def rewrite(root: Path, owner: str, dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for path in candidates(root):
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        updated = IN_URL.sub(owner, text)
        if updated == text:
            continue
        changed.append(path)
        if not dry_run:
            path.write_text(updated)
    return changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("owner", help="the GitHub account or organisation this repository lives under")
    parser.add_argument("--launcher", default="", help="path to the KyvoraLauncher clone, rewritten too")
    parser.add_argument("--dry-run", action="store_true", help="list the files that would change")
    args = parser.parse_args(argv)

    owner = args.owner.strip().strip("/")
    if not owner or "/" in owner or PLACEHOLDER in owner:
        print(f"'{args.owner}' is not an account name", file=sys.stderr)
        return 1

    roots = [RELEASES_ROOT]
    if args.launcher:
        launcher = Path(args.launcher).expanduser().resolve()
        if not (launcher / "project.godot").exists():
            print(f"{launcher} does not look like the launcher project", file=sys.stderr)
            return 1
        roots.append(launcher)
    # The launcher's own tooling is left to its own repository; this script only
    # ever substitutes one string, so running it twice is harmless.
    else:
        print("note: --launcher was not given, so the bundled catalog still names the placeholder")

    total = 0
    for root in roots:
        changed = rewrite(root, owner, args.dry_run)
        total += len(changed)
        for path in changed:
            print(f"  {'would rewrite' if args.dry_run else 'rewrote'} {path.relative_to(root)}")
        print(f"{root.name}: {len(changed)} files")
    if total == 0:
        print(f"nothing named {PLACEHOLDER}; already set?")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
