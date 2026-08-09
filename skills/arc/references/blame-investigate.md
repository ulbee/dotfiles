# Blame & Investigate Reference

## Blame (per-line authorship)

```bash
arc blame <file>                       # who changed each line
arc blame --json <file>                # JSON output (easier to parse programmatically)
arc blame -s <file>                    # compact: without date and author details
arc blame -r <file>                    # show SVN revision numbers alongside hashes
```

## File history

```bash
arc log -- <file>                      # all commits touching this file
arc log -n 10 -- <file>               # last 10 commits for a file
arc log --stat -- <file>              # with change stats
arc log --name-status -- <file>       # with A/M/D status
```

## Search by content changes

```bash
arc log -S "function_name"             # commits that added or removed this string
arc log -S "TODO" -- path/to/dir      # scoped to directory
```

## Search by commit message

```bash
arc log --grep "fix"                   # commits with "fix" in message
arc log --grep "TICKET-123"            # find commits referencing a ticket
```

## Search by author

```bash
arc log --author "username"            # commits by specific author
```

## Find which commit introduced a file

```bash
arc log trunk..HEAD --name-status      # files added/modified/deleted in branch
```

## Get merge-base (branch divergence point)

```bash
arc merge-base HEAD trunk              # hash where current branch diverged from trunk
```
