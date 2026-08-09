# Rebase & Sync Reference

## Sync with trunk

```bash
arc checkout trunk       # switch to trunk
arc pull                 # pull latest changes
arc checkout <branch>    # switch back to feature branch
arc rebase trunk         # rebase on top of fresh trunk
```

Or without switching:
```bash
arc pull trunk           # pull trunk while on any branch
arc rebase trunk         # rebase current branch onto trunk
```

## After rebase

Force push is required because rebase rewrites commit hashes:
```bash
arc push -f -u users/<login>/<branch>   # explicit branch name to avoid double prefix
```

## Conflict resolution during rebase

If `arc rebase trunk` produces conflicts:
1. `arc status` to see conflicted files
2. Edit each file, resolve `<<<<<<<` / `=======` / `>>>>>>>` markers
3. `arc add <resolved-files>`
4. `arc rebase --continue`
5. Repeat until all commits are replayed

To abort: `arc rebase --abort` (returns to pre-rebase state).

## Shared branch safety

Before force pushing on a branch where others may commit:
1. `arc pull` first to check for new commits
2. If new commits appear, rebase on top of them
3. Only then: `arc push -f -u users/<login>/<branch>`

On personal branches, force push is safe without pull.

## Pull options

```bash
arc pull                 # pull current branch
arc pull trunk           # pull trunk (can run from any branch)
arc pull --rebase        # pull + rebase instead of merge
```

## Recovery: undo a rebase

Previous branch state is saved in `ORIG_HEAD`:
```bash
arc reset --hard ORIG_HEAD
```

## Rebase --onto (change branch base)

When branch B was based on branch A, and you want B based on trunk instead:
```bash
arc rebase --onto trunk A B
```

General form: `arc rebase --onto <new-base> <old-base> <branch>`.

## Reflog (local state history)

```bash
arc reflog show -n 5    # last 5 state changes (checkout, rebase, reset, etc.)
```

Useful for debugging what happened to the repository.
