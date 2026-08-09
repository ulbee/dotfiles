# PR Review Reference

## Essential commands

```bash
arc pr status <pr-id>        # Get PR metadata (title, description, status)
arc pr changes <pr-id>       # View diff (use positional arg, not --id)
arc pr checkout <pr-id>      # Checkout PR branch
```

## Size-based review strategy

1. Get PR info and size: `arc pr status <pr-id>` and `arc pr changes <pr-id> | wc -l`
2. **Small PR (<2K lines):** parse `arc pr changes <pr-id>` output directly
3. **Large PR (>2K lines):** run `arc pr checkout <pr-id>` and read files directly

## Get file list from diff

```bash
arc pr changes <pr-id> | grep "^diff --git"        # All changed files
arc pr changes <pr-id> | grep "^new file"          # New files only
```
