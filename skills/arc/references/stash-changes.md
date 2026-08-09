# Stash Changes Reference

## Basic stash workflow

```bash
arc stash push -m "description"   # save uncommitted changes with label
arc stash pop                      # restore most recent stash and remove it
arc stash list                     # list all saved stashes
```

## Additional stash commands

```bash
arc stash drop                     # delete most recent stash without applying
arc stash apply                    # apply most recent stash without removing it
arc stash show                     # show diff of most recent stash
arc stash push -m "desc" -- file   # stash only specific files
```

## Common patterns

Save work before switching branches:
```bash
arc stash push -m "wip: feature X"
arc checkout trunk
# do other work
arc checkout <original-branch>
arc stash pop
```
