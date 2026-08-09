# Resolve Conflicts Reference

## Identify conflicts

```bash
arc status    # conflicted files show as "both modified" or "UU"
```

## Resolution workflow

1. Open each conflicted file
2. Find and resolve conflict markers:
   ```
   <<<<<<< HEAD
   your changes
   =======
   incoming changes
   >>>>>>> branch-name
   ```
3. Remove the markers, keep the correct code
4. `arc add <resolved-file>` for each resolved file
5. Continue the operation:

| Operation | Continue command |
|-----------|----------------|
| Rebase | `arc rebase --continue` |
| Cherry-pick | `arc cherry-pick --continue` |
| Merge | `arc commit` |
| Submit | `arc submit` |

## Abort

To abandon the operation and return to pre-conflict state:

| Operation | Abort command |
|-----------|-------------|
| Rebase | `arc rebase --abort` |
| Cherry-pick | `arc cherry-pick --abort` |
| Merge | `arc merge --abort` |
| Submit | `arc submit --abort` |

## Submit conflicts (special case)

`arc submit` handles conflicts differently:
- It squashes all branch commits into one before rebasing onto fresh trunk
- After resolution, the branch contains a single squashed commit
- If you need to preserve commit structure, abort and use regular rebase instead

See `submit-changes.md` for details.

## Auto-resolve with -X strategy

When you know which side should win conflicts:
```bash
arc rebase trunk -X theirs    # on conflict, keep current branch changes
arc rebase trunk -X ours      # on conflict, keep trunk changes
arc cherry-pick <hash> -X theirs
```

Note: during rebase, "theirs" means your branch (counterintuitive, because commits
are being replayed onto the target, so your changes become "theirs").

## Skip a problematic commit

During rebase or cherry-pick, skip the current commit instead of resolving:
```bash
arc rebase --skip           # skip current commit, continue with next
arc cherry-pick --skip      # skip current commit
```
