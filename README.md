# Kyvora releases

The update host for the [Kyvora Games Launcher](https://github.com/kyvoracloud-klyne/KyvoraLauncher). Public,
because the launcher fetches from it with no credentials.

Two kinds of thing live here, and the split is deliberate:

- **Small text documents, in git.** Channel pointers, the catalog, news and patch notes. They are served
  from `raw.githubusercontent.com`, which caches for a few minutes and imposes no rate limit, so a
  launcher can ask on every start without a token.
- **Build bytes, as GitHub Release assets.** Each asset is named after its own SHA-256, and a release
  contains **only the objects that are new in that version**. The manifest carries a full URL per file,
  so an unchanged file keeps pointing at the older release it was first published in. That is what makes
  an update download only what changed, with no object index to keep in sync.

```
catalog.json                     games the launcher offers
launcher/channels/stable.json    the launcher's own self-update pointer
games/voidfall/
  channels/stable.json           the version this channel points at, per platform
  channels/beta.json
  news.json                      the feed the launcher renders
  news/0.1.0.md                  patch notes, in markdown
tools/validate_documents.py      the launcher's rules, runnable in CI
tools/set_owner.py               fills the account name into every URL, here and in the launcher
```

## Before the first release

Every URL here names `KYVORA_OWNER`. Point them at the account that owns this repository, and the
launcher's bundled catalog with them — the two have to agree, or the launcher offers a game that can
never install:

```bash
python3 tools/set_owner.py your-github-name --launcher ../KyvoraLauncher
python3 tools/validate_documents.py
```

It only substitutes inside URLs, so the constants in `validate_documents.py` and `HostConfig.gd` that
exist to *detect* the placeholder keep working, and running it twice is harmless.

The channel pointers in git are seeded, not real: they name manifests for `voidfall-v0.1.0` and
`launcher-v0.1.0`, which do not exist until something publishes them. `tools/release/publish.py` in the
game repository creates the release, uploads the new objects and rewrites these pointers, so the first
run of it makes the pointers true.

## Publishing

From the game repository:

```bash
python3 tools/release/publish.py --version 0.1.1 --notes "Cover fixes" --releases-repo ../kyvora-releases
```

It exports the game for both platforms, hashes every output, diffs against the manifest of the previous
version, uploads only the objects whose hashes are new, and commits the updated channel pointer and news
entry back here. `--dry-run` does everything except the upload and the commit.

## Editing news by hand

`games/<id>/news.json` and the markdown under `games/<id>/news/` are meant to be edited directly — that
is the whole point of keeping them in git rather than behind a service. Two rules the validator enforces:

- Every URL must be `https://`. The launcher refuses anything else, and every byte a manifest names ends
  up executed on somebody's machine.
- An entry's `kind` is one of `news`, `patch_notes`, `hotfix` or `event`, and `date` is `YYYY-MM-DD`. The
  launcher sorts by date rather than trusting the file's order.

Run `python3 tools/validate_documents.py` before pushing, or let the `validate` workflow tell you.
