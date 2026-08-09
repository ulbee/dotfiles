# Check State Reference

## Current branch

```bash
arc info --json          # full info: branch, commit, author
arc info --json | python3 -c "import json,sys; print(json.load(sys.stdin)['branch'])"
```

Do NOT use `arc branch --show-current`, it does not exist in arc.

## Working tree status

```bash
arc status               # show modified, staged, untracked files
arc status -s            # short format
```

## Commit history

```bash
arc log -n 5             # last 5 commits (NOT arc log -5)
arc log --oneline        # compact format with full hashes
arc log --oneline -n 10  # compact, last 10
arc log -- path/to/file  # commits touching a specific file
arc log --stat -n 5      # with file change stats
```

Range notation works in `arc log` (unlike `arc diff`):
```bash
arc log trunk..HEAD      # commits on branch, excluding trunk
```

## Branch listing

```bash
arc branch -l            # local branches
arc branch -a            # all branches (local + remote)
arc branch -a -v         # all branches with hashes and subjects
arc branch --merged      # branches merged into HEAD
```

## Commit details

```bash
arc show <full-40-char-hash>          # show commit diff
arc show <full-hash> --stat           # show commit file stats
```

Note: `arc show COMMIT:path` is broken from subdirectories (see Monorepo Pitfalls in SKILL.md).

## Merge-base (branch divergence point)

```bash
arc merge-base HEAD trunk              # commit where branch diverged from trunk
```

## Log filters

```bash
arc log --author "username"            # commits by specific author
arc log --grep "pattern"               # search commit messages
arc log -S "string"                    # commits that added or removed a string
arc log --name-status -n 10            # recent commits with file A/M/D status
arc log trunk..HEAD --name-status      # files changed in branch
```

## Speed up status on diverged branches

```bash
arc status --no-ahead-behind           # skip ahead/behind calculation (faster)
```

## Clean working directory

```bash
arc clean                              # remove untracked files
arc clean -d                           # remove untracked files and directories
arc clean -Xd                          # remove only ignored files and directories
```

## Reflog (local state history)

```bash
arc reflog show -n 5                   # last 5 state changes
```

Shows checkout, rebase, reset, commit operations. Useful for understanding what happened.

## Version

```bash
arc --version
```
