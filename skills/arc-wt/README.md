---
name: arc-wt
description: Guides using the arc-wt helper to create and manage Arcadia worktrees, including build steps and naming/path conventions.
---

# arc-wt

Use this skill to build and operate the `arc-wt` helper that wraps Arcadia worktree setup.

## Find and build arc-wt

Arc-wt lives in this Arcadia repo at `ai/tools/arc_worktree/arc_wt/`.

Typical location on this machine:

```bash
~/arcadia-wt
```

From the Arcadia repo root:

```bash
ya make ai/tools/arc_worktree/arc_wt
```

The binary is built at:

```bash
ai/tools/arc_worktree/arc_wt/arc-wt
```

## Configuration

arc-wt supports configuration via `~/.config/arc-wt.yaml`:

```yaml
# Базовый путь для worktrees (default: ~/arcadia-wt)
worktrees_base_path: ~/arcadia-wt

# Базовый путь для stores (default: ~/.arc/stores)
stores_base_path: ~/.arc/stores

# Путь к object store (default: ~/projects/arc_obj_store)
object_store_path: ~/projects/arc_obj_store

# Путь к trunk репозиторию (default: ~/arcadia)
trunk_path: ~/arcadia

# Дефолтный режим: init, mount, mount-shared (default: mount-shared)
default_mode: mount-shared

# Хук после создания worktree (опционально)
post_create_hook: "echo 'Created $ARC_WT_NAME at $ARC_WT_PATH'"

# Хук перед удалением worktree (опционально)
pre_remove_hook: "echo 'Removing $ARC_WT_NAME from $ARC_WT_PATH'"
```

## Common workflow

Create a new worktree:

```bash
arc-wt add <branch>
```

List worktrees:

```bash
arc-wt list
```

Remove a worktree entry:

```bash
arc-wt remove <name>
```

Remount an entry:

```bash
arc-wt remount <name>
```

Show current configuration:

```bash
arc-wt config
```

## Naming and path conventions

- **Entry name**: use the branch name (for example `VERTISMOBMETA-984-tasklet`).
- **Mount path**: place worktrees under `~/arcadia-wt/<branch>`.
- **Store path**: default is `~/.arc/stores/<name>` unless `--store-path` is provided.
- **Object store (shared)**: for `--mode mount-shared`, default is `~/projects/arc_obj_store` unless `--object-store-path` is provided.

## Notes

- `arc-wt` records entries in `~/.config/arc-wt/state.json`.
- Configuration is read from `~/.config/arc-wt.yaml`.
- `--mode init` uses `arc init` instead of `arc mount` and does not use a store.
- `--mode mount-shared` mounts with a shared object store.
- Hooks `post_create_hook` and `pre_remove_hook` can be defined in config to run commands after creation and before removal.
