# Push Mechanics Reference

## Basic push

```bash
arc push -u users/<login>/<branch>    # first push: set upstream + push
arc push                               # subsequent pushes (upstream already set)
arc push --publish                     # push + auto-publish PR iteration
arc push --wait                        # push and wait until PR is updated in Arcanum
```

## Double prefix problem (detailed)

If local branch is `users/<login>/TICKET`, bare `arc push` prepends another
`users/<login>/`, creating `users/<login>/users/<login>/TICKET`.

Always specify the branch name explicitly:
```bash
arc push -u users/<login>/TICKET       # correct
arc push --force                        # WRONG: creates double prefix
arc push -f -u users/<login>/TICKET    # correct force push
```

## Force push safety

Force push rewrites remote history. Before force pushing on a shared branch:

1. `arc pull` first to check for other developers' commits
2. If pull reveals new commits you didn't make, rebase on top of them
3. Only then force push: `arc push -f -u users/<login>/<branch>`

On personal branches (only you work on them), force push is safe without pull.

## --set-upstream quirk

`arc push --set-upstream` without a branch argument breaks.
Always use the short form with explicit name: `arc push -u <branch-name>`.

## When force push is required

After any history-rewriting operation:
- `arc rebase`
- `arc commit --amend`
- `arc reset` (when commits were removed)
- Squash via `arc reset --soft HEAD~N` + recommit

## Common push errors

### "pushed 0 commit(s)"

Not an error. Arc push works in two phases: (1) upload commit objects, (2) move branch
pointer. If commits were already uploaded earlier (e.g., pushed to a wrong branch name),
the second push uploads 0 new commits but still moves the pointer correctly.
Verify with `arc pr list` that the PR looks right.

### "branch 'X' already exist and should be merged before update"

Remote branch diverged from local. Fix:
```bash
arc branch -u users/<login>/<branch>     # re-link local branch to remote
arc push -f -u users/<login>/<branch>    # force push (overwrites remote)
```
Warning: this overwrites the remote branch. If the remote has changes you need,
fetch them first into a separate branch.

### "branch 'X' should be merged into 'Y' before push"

Misleading message, arc has no merge operation. Fix: `arc push -f -u users/<login>/<branch>`.

### Pull after someone else's force push

When a collaborator force-pushed to your shared branch:
```bash
arc reset --hard arcadia/users/<login>/<branch>
```
