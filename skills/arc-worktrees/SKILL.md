---
name: arc-worktrees
description: Use when needing isolated workspace for parallel work in Arcadia - multiple Claude agents on different tasks, user working in IDE while agent works separately, or switching between tasks without losing state.
user-invocable: false
---

# Arc Worktrees — Isolated Workspaces in Arcadia

## Overview

Arc worktrees are **multiple `arc mount` points sharing one object-store** — the Arcadia analog of git worktrees. Each mount is an independent FUSE-based virtual filesystem with its own branch, letting multiple agents or a user+agent work in parallel without conflicts.

**Announce at start:** "Using arc-worktrees skill to set up an isolated workspace."

## When to Use

- Multiple Claude agents working on different tasks simultaneously
- User works in IDE on one task, Claude works on another in parallel
- Switching between tasks without stash/checkout dance
- Any time you need a second independent copy of Arcadia

**When NOT to use:**
- Single task, single branch — just work in existing mount
- Only need to switch between PRs — use `arc pr select` instead

## Pre-Flight Checks

Before creating a worktree, always run:

```bash
# 1. List existing mounts
arc mount --list

# 2. Check disk space (store is ~25-30GB typically)
du -sh ~/.arc/store

# 3. Check current branch in main mount
cd ~/arcadia && arc info
```

**NEVER create a worktree if disk space < 10GB free.** Each mount adds overlay storage.

## Creating a Worktree

### Step 1: Mount

```bash
arc mount ~/arcadia-worktrees/<NAME>
```

`<NAME>` convention: use ticket ID or descriptive slug (e.g. `PROJ-12345`, `fix-search-pagination`).

**Why `~/arcadia-worktrees/`:** Mount must be a top-level directory because `ya make`, IDE tooling, and `$ARCADIA_ROOT` resolve from mount root. Subdirectories of existing mounts won't work.

### Step 2: Create branch and navigate

```bash
cd ~/arcadia-worktrees/<NAME>
arc checkout -b users/<LOGIN>/<NAME>
cd <project/path>  # navigate to project root
```

### Step 3: Verify

```bash
arc info        # confirm branch
arc status      # confirm clean state
```

Report: "Worktree ready at `~/arcadia-worktrees/<NAME>/<project/path>` on branch `users/<LOGIN>/<NAME>`"

## Working in a Worktree

### Committing changes

```bash
arc status                          # see what changed
arc diff                            # review changes
arc add <file1> <file2>             # stage specific files
arc diff --cached                   # verify staged
arc commit -m "<TICKET>: description"
```

### Pushing branch to remote

```bash
arc push -u users/<LOGIN>/<NAME>    # first push: set upstream
arc push                            # subsequent pushes
```

## Cleanup (CRITICAL)

**Every worktree you create MUST be cleaned up.** Store grows with usage and is never auto-cleaned.

### Step 1: Verify work is complete

```bash
cd ~/arcadia-worktrees/<NAME>
arc status          # no uncommitted changes?
```

**If uncommitted changes exist, ask user before proceeding.**

### Step 2: Unmount

```bash
cd ~   # MUST exit the mount first
arc unmount ~/arcadia-worktrees/<NAME>
```

### Step 3: Remove storage (free disk space)

```bash
# Remove mount registration AND its overlay storage
arc unmount --forget ~/arcadia-worktrees/<NAME>

# Remove empty directory
rmdir ~/arcadia-worktrees/<NAME> 2>/dev/null
```

**`--forget` is irreversible.** Only use after confirming work is pushed/merged.

### Step 4: Garbage-collect shared store

```bash
arc gc              # remove objects that exist on server
arc gc --dry-run    # preview what would be removed
```

### Step 5: Clean up branches and build cache

```bash
cd ~/arcadia
arc checkout trunk
arc br -D --merged                  # delete local merged branches
ya gc cache                         # clean build cache (~/.ya/build)
```

### Disk usage reference

| Location | What | Cleanup |
|----------|------|---------|
| `~/.arc/store/.arc/objects` | Shared object store (~24GB) | `arc gc` |
| `~/.arc/store/` (overlay per mount) | Mount-specific changes | `arc unmount --forget` |
| `~/.ya/build/` | Build cache | `ya gc cache` |
| `~/.arc/traces/` | Command logs | Auto-cleaned (30-day TTL) |

## Safety Rules

| Rule | Why |
|------|-----|
| Never `grep`/`ya grep` without `--remote` from mount root | Downloads ALL of Arcadia, freezes account |
| Never open mount root in IDE without `ya project update` | IDE indexing downloads everything |
| Never `arc push -f` shared branches | Destroys colleagues' work |
| Never `arc unmount --forget` with uncommitted changes | Irreversibly loses work |
| Never `arc reset --hard` without confirming with user | Permanently deletes uncommitted changes |
| Always `cd ~` before `arc unmount` | Can't unmount from inside mount |
| Never `arc checkout`/`arc stash` in user's active mount as a workaround | Kills FUSE daemon, crashes IDE, loses user's and other agents' work |

## Quick Reference

| Action | Command |
|--------|---------|
| List mounts | `arc mount --list` |
| Create mount | `arc mount <path>` |
| Unmount | `arc unmount <path>` |
| Unmount + delete storage | `arc unmount --forget <path>` |
| Create branch | `arc checkout -b users/<login>/<name>` |
| GC store | `arc gc` |
| GC build cache | `ya gc cache` |
| Clean merged branches | `arc br -D --merged` |
| Check store size | `du -sh ~/.arc/store` |

## Troubleshooting

### Account frozen after mount creation
Arc FUSE downloads files on demand. If IDE or grep traverses the tree, massive traffic triggers account freeze. Go to Arcanum, click "Everything is OK, it's me", explain in SECALERTS ticket.

### `arc unmount` fails
1. Check no process uses the mount: `lsof +D ~/arcadia-worktrees/<NAME>`
2. Try force unmount: `arc unmount -f ~/arcadia-worktrees/<NAME>`
3. If still fails (stale FUSE mount on macOS): `diskutil unmount force ~/arcadia-worktrees/<NAME>`

### Disk space running out
```bash
du -sh ~/.arc/store           # check store size
arc gc                        # clean unreferenced objects
ya gc cache                   # clean build cache
arc mount --list              # find forgotten mounts
# unmount --forget any unused mounts
```

### Shell completion stale after arc update
```bash
arc completion zsh > ~/.zfunc/_arc    # regenerate
```
