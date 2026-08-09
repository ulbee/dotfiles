---
name: guru-code
description: Implements a Tracker issue autonomously by reading issue context and plan comments, making localized changes, and submitting the result through Arcadia VCS.
---

Use this skill when the user wants a Tracker issue executed end to end with minimal supervision.

Hard rule: use `arc` for VCS operations and do not fall back to `git`.

All human-facing communication for this skill must be in Russian: Tracker comments, progress updates, final report, and default commit/PR summaries.

Execution rules:

1. Gather authoritative context first:
   - extract the Tracker issue key or id from the prompt
   - call `tracker_get_issue`
   - call `tracker_get_issue_comments`
   - fetch links, changelog, or attachments before coding when they affect the implementation
2. Interpret issue comments by priority:
   - treat comments containing `<!-- auto-plan -->` or the heading `## Автономный план выполнения` as plan comments
   - treat human-written comments as strong guidance and let them override stale plan details when they conflict
   - treat the issue description as fallback context, not the only source of truth
3. Stay autonomous, but conservative:
   - prefer the smallest localized diff that satisfies the issue and latest human guidance
   - avoid opportunistic cleanup, broad refactors, dependency churn, mass formatting, or unrelated renames
   - if scope expands beyond the current plan, explain the scope change in the final report
4. Verify workspace state before editing:
   - run `arc status`
   - if unrelated local changes make safe work impossible, stop rather than overwrite or clean them
5. Branch and implement:
   - reuse the current branch only when it is clearly dedicated to the same issue
   - otherwise create and switch with `arc checkout -b <ISSUE-KEY>-<short-slug>`
   - inspect nearby code and tests, then implement the smallest viable change set
   - add or update tests when behavior changes and that area already has tests
6. Verify before commit:
   - review the final diff with `arc diff`
   - run the highest-signal verification loop that fits the touched code
   - do not claim success when verification was skipped or partial
7. Commit and resolve through Arcadia VCS:
   - stage only relevant files with `arc add <paths>`
   - commit with `<ISSUE-KEY>: <краткое повелительное описание>`
   - create the PR with `arc pr create --auto --no-edit --wait -m "<ISSUE-KEY>: <краткое резюме>"`
   - capture the PR id from `arc pr create` output, then run `arc pr status <PR_ID> --json` to get the url and merge status
8. Optional issue update:
   - if Tracker write tools are available, add or update a short issue comment with what changed, what was verified, and the PR link
9. Final response must include:
   - files changed
   - verification performed
   - commit hash
   - PR id or url, or the exact reason PR creation could not complete
   - remaining follow-ups or user decisions

Minimal arc commands for this skill:

```bash
arc status
arc checkout -b <ISSUE-KEY>-<short-slug>
arc diff
arc add <paths>
arc commit -m "<ISSUE-KEY>: <краткое повелительное описание>"
arc pr create --auto --no-edit --wait -m "<ISSUE-KEY>: <краткое резюме>"
arc pr status <PR_ID> --json
```

If issue context or human guidance is contradictory in a way that blocks safe execution, do all non-blocked discovery first and then ask exactly one targeted question.
