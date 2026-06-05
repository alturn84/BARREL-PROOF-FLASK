# DEPLOY-002: Data Ownership — Cron vs. Local Commits

## Summary

Barrel Proof has two categories of files in `Site Data/`:

1. **Cron-owned runtime data** — written daily by Hermes/cron scripts on the Render server
2. **Manually maintained schema files** — edited by hand, belong in git

Mixing these in commits causes merge conflicts when the server's cron push
and a local code commit touch the same files.

---

## Cron-Owned Files (do not commit locally)

These files are regenerated every morning by scheduled scripts.
Committing them locally will conflict with the server's next push.

```
Site Data/game_cards.json
Site Data/game_of_day.json
Site Data/game_to_watch.json
Site Data/around_the_league.json
Site Data/press_box.json
Site Data/schedule.json
Site Data/standings.json
Site Data/odds.json
Site Data/dope-sheet-data.json
```

All nine are listed in `.gitignore` under the `# DEPLOY-002` block.
Note: they are also currently tracked by git. See the "Cleanup" section below.

---

## What Belongs in Local Commits

| Path | Owner | Notes |
|---|---|---|
| `app.py`, `templates/`, `scripts/` | Developer | Code and templates |
| `Site Data/teams.json` | Developer | Manually maintained team schema |
| `Site Data/archive/` | update_archive.py | Intentional historical snapshots — commit after backfills |
| `media/lead-images/captions.json` | Developer | Manually maintained caption metadata |
| `Daily/*.md` | mlb_fetch.py | Commit after manual recovery runs |
| `.gitignore`, `docs/`, `README` | Developer | Project config |

---

## Before Every Commit

Run:
```bash
git status
```

If any `Site Data/` files appear as modified or staged:

- **If unintentional** (cron noise):
  ```bash
  git restore "Site Data/game_cards.json"
  git restore "Site Data/standings.json"
  # etc.
  ```

- **Or use the check script:**
  ```bash
  python3 scripts/check_clean_commit.py
  ```

---

## If a Site Data Schema Change Is Intentional

For example, adding a field to `teams.json`:

1. Make the change
2. Note it explicitly in the commit message:
   ```
   git commit -m "Add nickname field to Site Data/teams.json (schema update)"
   ```
3. To force-add a normally-ignored file:
   ```bash
   git add -f "Site Data/teams.json"
   ```

---

## Do Not Use `git add .` Blindly

`git add .` will stage everything in the working tree, including cron-updated
files that have drifted from HEAD since the last server push. Always stage
files by explicit path or use `check_clean_commit.py` before staging.

---

## Cleanup: Untracking Already-Tracked Cron Files

The cron-generated files listed above are still tracked by git (they were
committed in the initial bootstrap). `.gitignore` only prevents *untracked*
files from being accidentally staged — it does not stop git from showing
changes to already-tracked files.

To fully stop tracking them (without deleting the files):

```bash
git rm --cached "Site Data/game_cards.json"
git rm --cached "Site Data/game_of_day.json"
git rm --cached "Site Data/game_to_watch.json"
git rm --cached "Site Data/around_the_league.json"
git rm --cached "Site Data/press_box.json"
git rm --cached "Site Data/schedule.json"
git rm --cached "Site Data/standings.json"
git rm --cached "Site Data/odds.json"
git rm --cached "Site Data/dope-sheet-data.json"
git commit -m "DEPLOY-002: untrack cron-generated Site Data files"
```

After this commit, changes to those files will be silently ignored by git
locally, and the server's cron pushes will no longer conflict with local
code commits.

---

*Document created: DEPLOY-002*
