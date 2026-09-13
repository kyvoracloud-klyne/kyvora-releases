# Kyvora releases

The update host for the [Kyvora Games Launcher](https://github.com/KYVORA_OWNER/KyvoraLauncher). Public,
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
```

## Before the first release

Every document here still names `KYVORA_OWNER`. Replace it with the GitHub account that owns this
repository, in this file and in every JSON document:

```bash
grep -rl KYVORA_OWNER . | xargs sed -i 's/KYVORA_OWNER/your-github-name/g'
python3 tools/validate_documents.py
```

The same name has to be filled into `data/launcher.json` and `data/games/voidfall.json` in the launcher
repository, which is the only place the launcher names its host.

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
