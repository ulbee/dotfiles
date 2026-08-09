# Diff & Code Review Reference

## `arc diff -B` vs `arc diff trunk`

These are fundamentally different operations:

- **`arc diff trunk`** - direct tree diff between trunk and HEAD. If trunk diverged by thousands of commits, the diff is huge and may hang.
- **`arc diff -B`** - computes merge-base and shows only changes introduced by the branch. Compact and fast regardless of divergence.

For code review, almost always use `-B` (what the PR will introduce).

## `-B` explained

Shows `merge-base(FROM, TO)` to `TO`. Default: FROM=trunk, TO=HEAD. This is exactly what your PR will introduce.

## Verified syntax (experimentally tested)

| Command | Result |
|---------|--------|
| `arc diff -B` | Works |
| `arc diff -B --stat` | Works, stable <1s |
| `arc diff trunk HEAD` (positional args) | Works |
| `arc diff --stat trunk HEAD` | Works |
| `arc diff --stat trunk` (single ref) | Works, but hangs when >3000 commits divergence |
| `arc diff trunk..HEAD` (range notation) | **Silent empty output** |
| `arc diff --stat trunk..HEAD` | **Silent empty output** |
| `arc log --stat trunk..HEAD` | Works (range notation is OK in `arc log`) |

## Diff flags

| Flag | Purpose |
|------|---------|
| `-B` / `--base` | Merge-base diff (what will merge) |
| `--cached` | Staged changes only |
| `--stat` | Summary: files/+/- counts |
| `--name-only` | Filenames only |
| `--name-status` | Filenames + A/M/D status |
| `-w` | Ignore whitespace |

## Common diff patterns

```bash
arc diff -B                    # Review all branch changes (DEFAULT for reviews)
arc diff -B --stat             # Quick overview first
arc diff --cached              # Before committing
arc diff                       # Unstaged changes
arc diff -B -- path/to/file    # Specific file
```
