---
name: arc
description: >
  Use this skill for ANY version control action in an Arcadia monorepo.
  This includes explicit VCS commands AND coding tasks that touch VCS concepts,
  such as displaying branch names, organizing code changes into multiple commits,
  or building features that reference branches.
  Trigger when you see ANY of these signals: Russian VCS words in any form
  (коммит/коммиты/коммитом, ветка/ветки/ветку/текущая ветка, пуш/запушь, транк),
  "trunk" as a branch name, SHCP-* identifiers even as examples (e.g., SHCP-1234),
  a.yandex-team.ru links, 8-digit PR IDs, "arc" CLI, or git commands
  (git log, git push) that may target an arc repo.
  Operations covered: branch, commit, push, pull, rebase, PR create/review/split,
  diff, log, squash, stash, revert, blame, status, current branch info.
  Detect arc repo: .arc/ directory, .arcignore, or a.yaml at root.
  Do NOT use for GitHub (github.com, `gh` CLI, PR #NNN), GitLab, SVN repos,
  SVG arcs, architecture topics, or Noah's Ark.
user-invocable: false
---

# Arc VCS — Background Knowledge

Arc is a lightweight version control system for Arcadia monorepo. It stores data in the cloud and uses virtual filesystem instead of downloading the entire repo.

## Detecting an Arc Repository

A project uses arc (NOT git) if ANY of these are true:
- `.arc/` directory exists at the repo root
- `.arcignore` file exists
- `a.yaml` file exists (Arcadia CI configuration)

When arc is detected: NEVER use `git` or `gh` commands. Use `arc` CLI instead.
If an `arc` command fails with an unexpected error, check the correct syntax with `arc <command> --help` before retrying.

## Key Differences from Git

- **Always use full hashes** — short SHAs yield `ambiguous` in a monorepo with millions of objects. `arc log --oneline` prints full hashes, copy them as-is
- **Main branch is `trunk`** (not `main` or `master`)
- **Branch naming:** `users/<username>/<branch-name>` for server branches
- **Lazy fetch:** no need to run `arc fetch` before `pull`/`checkout`, it happens automatically
- **`arc cp`** preserves copy history, use it instead of plain file copy when moving/copying tracked files
- **`.arcignore`** uses the same format as `.gitignore`
- **PR target** defaults to `trunk`
- **`arc submit`** = create branch + commit + push + create PR in one command
- **`arc info --json`** shows current branch, commit hash, author info

## Scenarios

### Push changes
When user asks to push, commit, or send changes:
1. `arc status` — check working directory
2. `arc add <specific-files>` — stage changed files (never `arc add .`)
3. `arc commit -m "message"` — commit with descriptive message (always pass -m)
4. `arc push -u users/<login>/<branch>` — push with explicit branch name (avoids double prefix)
5. **Shared branch safety:** before force push, `arc pull` first to check for others' commits

For push mechanics and double prefix details, read `references/push-changes.md`.

### Create or update PR
When user asks to create a PR or send for review:
1. Ensure changes are committed and pushed
2. `arc pr create --publish -m "description"` — create PR (never without -m, it opens an editor)
3. For updating: just push new commits, PR updates automatically
4. Or use `arc submit -m "description"` for streamlined flow (branch + commit + push + PR)
5. For auto-merge after checks: add `--merge` flag to `arc pr create`
6. For release branch PR: `arc pr create --publish --to <release-branch> -m "desc"`

For all PR flags (--merge, --auto, --to, --stack), stacked PRs, and release branch targeting, read `references/create-update-pr.md`.

### Submit changes (streamlined)
When user wants the simplest path from code to PR:
1. `arc submit -m "description"` — from trunk: creates branch + commits all tracked files + pushes + creates PR
2. `arc submit` — from existing submit-branch: commits + pushes + updates PR iteration (no -m needed)
3. `arc submit -m "desc" path/to/file` — submit only specific files
4. If conflicts: resolve files, `arc add <files>`, then `arc submit` again (or `arc submit --abort`)
5. `arc submit --new -m "desc"` — create independent PR from same trunk point
6. `arc pr select` — TUI to switch between submit-created branches (requires TTY)

For conflict handling details, --stack, and branch naming, read `references/submit-changes.md`.

### Review a PR
When user asks to look at, review, or check a PR:
1. `arc pr status <pr-id>` — get PR metadata (do NOT use `arc pr view`, it opens browser)
2. `arc pr changes <pr-id> | wc -l` — assess PR size
3. Small PR (<2K lines): `arc pr changes <pr-id>` — read diff directly
4. Large PR (>2K lines): `arc pr checkout <pr-id>` — checkout and read files
5. Get changed file list: `arc pr changes <pr-id> | grep "^diff --git"`

For review strategy details, read `references/review-pr.md`.

### Diff and code review
When user asks for diff, changes, or code review:
1. `arc diff -B` — merge-base diff (what PR will introduce). DEFAULT for reviews
2. `arc diff -B --stat` — quick overview with file/line counts
3. `arc diff -B --name-only` — only filenames (what changed in the branch)
4. `arc diff -B -- path/to/file` — specific file diff
5. Never `arc diff trunk` — direct diff, hangs on large divergence (>3000 commits)
6. Never range notation `arc diff trunk..HEAD` — silently gives empty output

For verified syntax table and all diff flags, read `references/review-diff.md`.

### Switch branches
When user asks to switch, checkout, or go to a branch:
1. `arc checkout <branch>` — switch to local branch
2. `arc checkout users/<login>/<TICKET>` — switch to ticket branch (lazy fetch pulls from server)
3. `arc checkout -b <name> trunk` — create new branch from trunk
4. `arc branch -d <name>` — delete local branch (NEVER `arc branch <name>` without flag, it creates!)
5. `arc push -d users/<login>/<branch>` — delete remote branch
6. Never search with `arc branch -a | grep` — try direct checkout first

For branch listing, renaming, deletion, and shared branch safety, read `references/switch-branches.md`.

### Check state
When user asks about current status, branch, or recent history:
1. `arc info --json` field `branch` — current branch (NOT `arc branch --show-current`)
2. `arc status` — working tree status
3. `arc log -n 5` — last 5 commits (NOT `arc log -5`)
4. `arc branch -a -v` — all branches with hashes

For arc info fields, log options, range notation, and commit details, read `references/check-state.md`.

### Rebase and sync
When user asks to rebase, sync, or update from trunk:
1. `arc checkout trunk` + `arc pull` — switch to trunk and pull latest
2. `arc rebase trunk` — rebase current branch on trunk
3. If conflicts: resolve, `arc add <files>`, `arc rebase --continue`
4. `arc push -f -u users/<login>/<branch>` — force push after rebase (explicit branch name)
5. **Shared branch safety:** before force push, `arc pull` to check for others' commits
6. If rebase went wrong: `arc reset --hard ORIG_HEAD` restores pre-rebase state

For step-by-step rebase workflow, --onto, recovery, and shared branch safety, read `references/rebase-sync.md`.

### Stash changes
When user needs to save work temporarily:
1. `arc stash push -m "description"` — save uncommitted changes with label
2. `arc stash pop` — restore the most recent stash
3. `arc stash list` — view saved stashes

For stash apply vs pop, partial stash, and common patterns, read `references/stash-changes.md`.

### Reorganize commits
When user wants to squash, amend, or restructure commit history:
1. **Amend last commit:** `arc add <files>` + `arc commit --amend`
2. **Squash N commits:** `arc reset --soft HEAD~N` + `arc commit -m "combined message"` (works in non-interactive shell)
3. **Interactive rebase:** `arc rebase -i HEAD~N` exists but requires TTY (opens editor), suggest user runs manually
4. **Cherry-pick:** `arc cherry-pick <full-40-char-hash>` (always full hash)
5. After any history rewrite: `arc push -f -u users/<login>/<branch>` (force push required)

For commit options, reset modes, cherry-pick, and squash details, read `references/reorganize-commits.md`.

### Resolve conflicts
When rebase, cherry-pick, or merge produces conflicts:
1. `arc status` — identify conflicted files
2. Open each file, resolve `<<<<<<<` / `=======` / `>>>>>>>` markers
3. `arc add <resolved-files>` — mark as resolved
4. Continue: `arc rebase --continue` / `arc cherry-pick --continue` / `arc commit`
5. To abort: `arc <operation> --abort`
6. Auto-resolve: `arc rebase trunk -X theirs` keeps branch changes on conflict, `-X ours` keeps trunk

For per-operation continue/abort, --skip, -X strategies, and submit conflict specifics, read `references/resolve-conflicts.md`.

### Revert and undo
When user wants to undo a commit or discard file changes:
1. `arc revert <full-hash>` — create a reverse commit (safe, preserves history)
2. `arc checkout <file>` — discard uncommitted changes in a file (do NOT use `--` separator, see Gotchas)
3. `arc checkout <COMMIT> <file>` — restore file to state at a specific commit (do NOT use `--` separator)
4. `arc reset --hard ORIG_HEAD` — undo last rebase or reset operation

For revert with conflicts, file recovery patterns, and reset modes, read `references/revert-undo.md`.

### Blame and investigate
When user asks who changed code, when something broke, or to search history:
1. `arc blame <file>` — show per-line authorship (`--json` for structured output)
2. `arc log -- <file>` — commits that touched a specific file
3. `arc log -S "string"` — find commits that added or removed a string
4. `arc log --grep "pattern"` — search commit messages

For blame flags, log filters, and history search patterns, read `references/blame-investigate.md`.

## Gotchas: arc ≠ git

Arc accepts many git-style flags without error but produces wrong or empty output. Others fail with cryptic messages. Before using an unfamiliar flag, run `arc <command> --help`. The table below lists the most common traps.

| Goal | git / gh (WRONG for arc) | arc (CORRECT) |
|------|--------------------------|---------------|
| Strip ANSI colors from PR list | `arc pr list --no-color` | `arc pr list` (no ANSI by default; `--no-color` is unsupported) |
| List only my PRs | `arc pr list --mine` | `arc pr list -o` |
| Log excluding trunk commits | `arc log HEAD --not trunk` | `arc log trunk..HEAD` |
| View PR details in terminal | `arc pr view <id>` (opens browser) | `arc pr status <id>` or `arc pr list --ticket <KEY> --json` |
| Three-dot diff | `arc diff trunk...HEAD` (silent empty output) | `arc diff -B --stat` |
| Last N commits | `arc log -5` | `arc log -n 5` |
| Custom log format | `arc log --format="%H %s"` (prints literal string) | `arc log --oneline` or `arc log --format="{commit.short} {title}"` (arc-style, experimental) |
| Get current branch name | `arc branch --show-current` | `arc info --json` field `branch` |
| Range notation in diff | `arc diff trunk..HEAD` (silent empty output) | `arc diff -B` or `arc diff trunk HEAD` (positional args) |
| Diff stat vs trunk | `arc diff --stat trunk` | Hangs when trunk diverged >3000 commits. Use `arc diff -B --stat` (stable <1s) |
| Extract file from a commit | `arc show COMMIT:path/file` from a subdirectory | **Broken from subdirectory** — arc prepends CWD to the argument. See Monorepo Pitfalls |
| Push a branch with `users/` prefix | `arc push --force` (on branch `users/<login>/...`) | Arc auto-prepends `users/<login>/` causing double prefix. Use `arc push -f -u users/<login>/<branch>` with explicit name |
| Checkout a ticket branch | `arc branch -a \| grep TICKET` | Directly `arc checkout users/<login>/<TICKET>`, lazy fetch will pull from server |
| Create PR without interactive editor | `arc pr create` (without -m) | Without `-m` arc opens an editor. Always use `arc pr create -m "..."` |
| Push with set-upstream | `arc push --set-upstream` (without parameter) | Breaks. Use `arc push -u <branch-name>` instead |
| Squash commits (non-interactive) | `arc rebase -i` (works but opens editor, requires TTY) | `arc reset --soft HEAD~N` + `arc commit -m "msg"` (no editor, works in scripts and CI) |
| Separate revision from paths | `arc checkout <COMMIT> -- <file>` | `arc checkout <COMMIT> <file>` — arc treats `--` as a literal file path (error: `path '--' did not match`). Never use `--` with arc checkout |
| Extract blob by ref | `arc cat-file blob <ref>` | No equivalent. Use `arc checkout <COMMIT> <file>` to restore into working directory, or `arc show <COMMIT>:<path>` from repo root |

## Monorepo Pitfalls

In Arcadia you almost always work from a subdirectory, not from the repo root.

### `arc show COMMIT:PATH` — broken from a subdirectory

Arc prepends CWD to the entire argument, including the hash. From `/repo/services/myservice/`, `arc show abc123:file.js` looks for `services/myservice/abc123:file.js`.

**Workarounds (simplest first):**
1. **`cp` before reset** — if files are in the working directory, copy to `/tmp` first
2. **`arc checkout <COMMIT> <path>`** — restores file into working directory (do NOT use `--` separator)
3. **Run from repo root** — `cd` to root, run `arc show`, then return

### Short hashes are ambiguous

In a monorepo with millions of objects, a 7-character SHA yields `TooManyResults: short SHA1 is ambiguous`. If a user provides a short hash, do NOT pass it to arc commands directly. Find the full hash first:

```bash
arc log --oneline | grep "^a1b2c3d"    # find full hash by prefix
# then use the full 40-character hash in subsequent commands
```

### `arc push` doubles the prefix for `users/` branches

If branch is `users/<login>/TICKET`, bare `arc push` creates `users/<login>/users/<login>/TICKET`. Always use `arc push -f -u users/<login>/TICKET` with explicit name.

For detailed push mechanics, read `references/push-changes.md`.

## Self-Check Rules

1. **Don't guess flags** — if a flag is borrowed from git by analogy, check `arc <command> --help` first.
2. **Checkout ticket branches directly** — don't search via `arc branch -a` and grep. Try `arc checkout users/<username>/<TICKET>` directly. Lazy fetch will pull from server.
3. **Empty output = suspicious** — in git, empty output usually means "no changes". In arc it often means "wrong syntax". If a command ran without errors but produced no output, double-check the syntax.
4. **Use `--json`** — reliable way to get data from `arc pr list`. Parse with `python3 -c "import json ..."`.
5. **Full hashes required** — if user gives a short hash, resolve it to full 40-char via `arc log --oneline | grep` before passing to any arc command.
6. **Keep it simple** — if files are already in the working directory, use `cp` to `/tmp` instead of `arc show COMMIT:PATH`.
