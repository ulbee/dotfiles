# Revert & Undo Reference

## Revert a commit

```bash
arc revert <full-40-char-hash>    # creates a new commit that reverses the changes
```

If revert produces conflicts:
1. Resolve conflicts in affected files
2. `arc add <resolved-files>`
3. `arc revert --continue`

To abort: `arc revert --abort`
To skip a problematic commit: `arc revert --skip`

## Discard file changes

```bash
arc checkout <file>                     # discard uncommitted changes (revert to HEAD)
arc checkout <COMMIT> <file>            # restore file to state at specific commit
arc checkout trunk <file>               # restore file to trunk version
```

**WARNING:** Do NOT use `--` as a separator between revision and file paths.
Unlike git, arc interprets `--` as a literal file path, causing errors like
`error: path '--' did not match any file(s) known to arc`. Pass revision and
paths as positional arguments without any separator.

## Undo last rebase or reset

```bash
arc reset --hard ORIG_HEAD    # ORIG_HEAD stores pre-rebase/pre-reset state
```

Use when rebase went wrong or `arc reset` was too aggressive.

## Reset modes

| Command | Index | Working tree | Use case |
|---------|-------|-------------|----------|
| `arc reset --soft HEAD~1` | Keeps staged | Keeps changes | Redo commit message or combine commits |
| `arc reset --mixed HEAD~1` | Unstages | Keeps changes | Redo staging (default mode) |
| `arc reset --hard HEAD~1` | Resets | Resets | Discard everything (DESTRUCTIVE) |

## Recovery after accidental commit to trunk

Arc forbids commits to trunk by default, but if it happened:

```bash
arc checkout -b <new-branch>           # save current state to a new branch
arc checkout trunk
arc reset --hard arcadia/trunk         # reset local trunk to remote state
```

If `arc reset --hard` fails with "cannot reset branch 'trunk'", temporarily allow commits
to trunk via `.arcconfig`, reset, then re-enable the restriction.
