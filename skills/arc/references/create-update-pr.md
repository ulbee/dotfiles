# Create & Update PR Reference

## Create PR (streamlined)

```bash
arc checkout trunk
# make changes
arc submit -m "PR title and description"
```

`arc submit` = create branch + commit + push + create PR in one command.

## Create PR (step by step)

```bash
arc checkout -b my-feature trunk
# make changes
arc add <specific-files>
arc commit -m "commit message"
arc push -u users/<login>/my-feature
arc pr create --publish -m "PR description"
```

## Update an existing PR

Push new commits. The PR updates automatically.
```bash
arc add <specific-files>
arc commit -m "update"
arc push
# or: arc push --publish   # push + auto-publish iteration
# or: arc submit
```

## PR flags

| Flag | Effect |
|------|--------|
| `--publish` | Publish review iteration immediately (default: `upload`) |
| `--publish=ci-success` | Auto-publish iteration only after CI passes |
| `-m "desc"` | Set description. **Always pass** to avoid interactive editor |
| `--merge` | Auto-merge after all checks pass |
| `--auto` | Equivalent to `--merge --publish --no-code-review` |
| `--to <branch>` | Target branch (default: trunk) |
| `--stack` | Create stacked PR (depends on current branch's PR) |
| `--new` | Force create new PR instead of updating current (arc submit only) |
| `-r USER` | Add reviewer (can be used multiple times) |
| `--label LABEL` | Add label (can be used multiple times) |

## PR to release branch

When targeting a branch other than trunk:
```bash
arc pr create --publish --to releases/2024.1 -m "Cherry-pick fix for release"
```

## Stacked PRs

For dependent changes split across multiple PRs:
```bash
# On first feature branch, PR already exists
arc checkout -b second-feature
# make changes
arc submit --stack -m "Part 2: depends on first-feature"
```

## Close/discard a PR

```bash
arc pr discard --id <pr-id>
```

Closes the PR without merging.

## Find PR for current branch

```bash
arc pr list                            # shows PRs related to current branch
arc pr status --branch <branch-name>   # PR info for a specific branch
```
