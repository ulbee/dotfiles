# Switch Branches Reference

## Branch commands

```bash
arc branch -l              # list local branches
arc branch -a              # list all branches (local + remote)
arc branch -a -v           # list all branches with hash and subject
arc branch <name>          # create a new branch from HEAD
arc branch <name> <start>  # create a new branch from <start>
arc branch -d <name>       # delete branch (only if merged/pushed)
arc branch -D <name>       # force delete branch
arc branch -m <old> <new>  # rename branch
arc branch --merged        # list branches merged into HEAD
```

DANGER: `arc branch <arg>` without a flag creates a branch named `<arg>`.
Always use flags like `-l`, `-d`, `-D`. Never pass a bare word unless you intend to create a branch.

## Shared branch awareness

When multiple developers work on the same `users/` branch:
- Before force push: `arc pull` first to check for others' commits
- If pull reveals new commits from other devs, rebase your work on top
- Only then force push: `arc push -f -u users/<login>/<branch>`
- When in doubt, ask the user whether the branch is shared

## Branch naming conventions

- Feature branches: `users/<login>/<ticket-or-name>`
- Server branches auto-prefixed with `users/<login>/` on push
- Do NOT manually add the prefix if arc adds it automatically (see double prefix pitfall in SKILL.md)

## Rename a branch

```bash
arc branch -m old-name new-name
```

This only renames the local ref. If already pushed, delete old remote and push new.

## Delete remote branch

```bash
arc push -d users/<login>/<branch>
```

## Delete all merged local branches

```bash
arc branch --merged trunk | grep -v trunk | xargs -L 1 arc branch -d
```

Or shorter: `arc branch --merged -d`

## Recovery: accidental commit to trunk

If `arc pull trunk` shows "branches are diverged and should be merged":

```bash
arc checkout -b <new-branch>           # save current state to new branch
arc checkout trunk
arc reset --hard arcadia/trunk         # reset local trunk to remote state
```
