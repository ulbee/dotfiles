# Reorganize Commits Reference

## Commit options

- `arc commit -m "message"` - commit staged changes
- `arc commit -a -m "message"` - stage all tracked + commit
- `arc commit --amend` - amend previous commit (rewrites history, needs force push)
- `arc commit --no-verify` - skip pre-commit hooks
- Always use `arc add <specific-files>` over `arc add .` when possible

## Amend last commit

```bash
arc add <files>
arc commit --amend
arc push -f -u users/<login>/<branch>   # force push required after amend
```

## Cherry-pick

```bash
arc cherry-pick <full-40-char-hash>   # apply a single commit to current branch
```

Always use full 40-character hashes (short hashes are ambiguous in monorepo).

If cherry-pick conflicts:
1. Resolve conflicts in affected files
2. `arc add <resolved-files>`
3. `arc cherry-pick --continue`

To abort: `arc cherry-pick --abort`

## Reset

```bash
arc reset HEAD~1            # undo last commit, keep changes staged
arc reset --soft HEAD~1     # undo last commit, keep changes staged
arc reset --hard HEAD~1     # undo last commit, discard all changes (DESTRUCTIVE)
arc reset <file>            # unstage a file
```

## Squash commits

**Option 1: Reset + recommit** (works in non-interactive shell, recommended for Claude Code):
1. `arc reset --soft HEAD~N` (N = number of commits to combine)
2. `arc commit -m "combined message"`
3. `arc push -f -u users/<login>/<branch>`

**Option 2: Interactive rebase** (requires TTY, suggest user runs manually):
```bash
arc rebase -i HEAD~N           # opens editor with pick/squash/fixup/reword/edit/drop
# mark commits as "squash" or "fixup", save and close
arc push -f -u users/<login>/<branch>
```

Also supports `--autosquash` with `arc commit --fixup COMMIT` and `arc commit --squash COMMIT`.

## Squash all branch commits (when N is unknown)

When you don't know how many commits to squash:
```bash
arc reset --soft $(arc merge-base trunk HEAD)
arc commit -m "squashed message"
arc push -f -u users/<login>/<branch>
```

`arc merge-base trunk HEAD` returns the commit where the branch diverged from trunk,
so this squashes everything into one commit regardless of how many there are.

Common use case: accidentally committed a secret, next commit removes it,
squash both to hide the secret from branch history.

## Auto-squash at PR merge

When a PR with multiple commits is merged in Arcanum, all commits are automatically
squashed into one. Manual squashing before merge is optional.
