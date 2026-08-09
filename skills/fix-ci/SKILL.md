---
name: fix-ci
description: Diagnose and fix failed CI checks on Arcanum PRs. Gets check statuses, analyzes failures, fetches CI logs from Sandbox, and applies fixes.
trigger: Use when the user asks to fix CI, check CI status, diagnose PR checks, fix failing builds/tests, or mentions "кубики" in relation to PRs.
arguments: PR_ID or PR URL, e.g. 11490907 or https://arcanum.yandex-team.ru/review/11490907/merge-checks
---

# Fix CI Skill

Diagnose and fix failed CI checks on Arcanum pull requests.

## Input Parsing

Extract PR_ID from the argument:
- If numeric: use directly as PR_ID
- If URL containing `/review/DIGITS`: extract the numeric ID
- If no argument: check if we're in an arc worktree and get PR ID from `arc pr list`

## Process

### Step 1: Get check statuses

```bash
arcanum-cli.sh checks PR_ID --active
```

This shows all failed and pending checks. Display the results to the user as a summary table.

### Step 2: Categorize failures

Group checks into categories:

**Arcanum checks** (system=`arcanum`):
- `comment_issues_closed` — there are unresolved review issues. List them:
  ```bash
  arcanum-cli.sh open-issues PR_ID
  ```
- `published` (pending) — PR is in draft. User needs to publish.
- `approved` — needs more approvals. Informational only.

**CI checks** (system=`CI` or `ci`):
- Checks with description containing "commits behind trunk" — branch is outdated, needs rebase
- Checks with `system_check_uri` — have CI flow with Sandbox tasks that contain logs
- Build failures — likely code compilation errors
- Test failures — test code issues
- Lint/analysis failures — code style or static analysis issues

**No-conflicts check:**
- `No conflicts` failure — merge conflicts need resolution

### Step 3: Get CI error logs from Sandbox

CI jobs run as Sandbox tasks. Use `sandbox-cli.sh` or `arcanum-cli.sh` wrappers to get error details.

**Quick approach — analyze all failed tasks at once:**
```bash
sandbox-cli.sh failed PR_ID
```
This finds all FAILURE tasks for the PR and runs smart error analysis on each.

**Step-by-step approach:**

1. **Find Sandbox task IDs** for the failed check:
   ```bash
   arcanum-cli.sh ci-jobs PR_ID "CHECK_TYPE"
   ```

2. **Smart error analysis** — parses execution.log for dart format failures, test errors, build errors, analyzer errors:
   ```bash
   sandbox-cli.sh errors TASK_ID
   ```

3. **Raw logs** from a Sandbox task:
   ```bash
   sandbox-cli.sh log TASK_ID                    # execution_error.log + error grep
   sandbox-cli.sh log TASK_ID execution.log      # full execution log (tail 100)
   ```

4. **Search full execution.log** for specific patterns:
   ```bash
   sandbox-cli.sh search-log TASK_ID "PATTERN" [CONTEXT_LINES]
   ```
   Useful when `errors` doesn't catch the issue. Searches up to 5MB of execution.log with grep -i.

5. **Access artifacts** (S3-uploaded files like execution_error_block.txt):
   ```bash
   sandbox-cli.sh artifact TASK_ID TASK_LOGS execution_error_block.txt
   sandbox-cli.sh artifact TASK_ID TEAMCITY_ARTIFACTS
   ```

### Step 3.5: Ensure worktree for applying fixes

Before applying any code fixes, ensure we're working in a worktree for this PR (never edit ~/arcadia directly):

1. Check if we're already in a worktree for this PR branch
2. If not, create one:
   ```bash
   arcanum-cli.sh worktree-create PR_ID
   ```
3. List existing worktrees:
   ```bash
   arcanum-cli.sh worktree-list
   ```

### Step 4: Propose and apply fixes

Based on the error analysis:

1. **Branch outdated** ("commits behind trunk"):
   - Tell user to run `arc rebase` and push
   - CI will automatically re-run after push

2. **Open review issues**:
   - Show the issues with file locations
   - Read the relevant files and propose fixes
   - After fixing, close the issues via:
     ```bash
     arcanum-cli.sh close-issue COMMENT_ID
     ```

3. **Build/test failures** (from Sandbox logs):
   - Parse error messages from `execution_error.log`
   - Common patterns:
     - `Error: 'X' is imported from both...` — import conflict, add `show`/`hide` or alias
     - `error: ...` in Dart/Swift — compilation error
     - `** ARCHIVE FAILED **` — iOS build failure
     - `BUILD FAILED` — general build failure
   - Read relevant source files and propose code fixes
   - Remind user to commit and push

4. **Lint/style failures** (e.g. `RT_STYLE_SUITE_CHECK`, `clang-format`, `ruff`, `dart format`):
   - These appear as sub-checks inside build/test suites with `CATEGORY_CHANGED` and `STATUS_FAILED`
   - To see style errors in detail, check the Arcanum UI: PR → Details → filter by `suiteCategory(CATEGORY_CHANGED)` and `status(STATUS_FAILED)`
   - Or get logs via Sandbox:
     ```bash
     sandbox-cli.sh errors TASK_ID    # parses format errors from execution.log
     sandbox-cli.sh search-log TASK_ID "style\|format\|clang-format\|ruff" 5
     ```
   - **Fix locally** by running the appropriate formatter in the worktree:
     - **backend-cpp / backend-go**: `cd <worktree>/<service-dir> && ya style .`
     - **mobile (Dart/Flutter)**: `cd <worktree>/<package-dir> && fvm dart format .`
   - Commit the formatting fix and push

### Step 5: Verify

After applying fixes:
- Re-check if there are remaining actionable items
- Remind user to `arc push` if changes were made locally
- Note that CI checks will re-run automatically after push

## Output Format

Present results as:

```
## PR #ID CI Status

### Failed Checks (X)
- [type] description — action needed

### Pending Checks (X)
- [type] description — waiting for...

### Diagnosis
[Analysis of what's wrong and why, including error messages from CI logs]

### Fix Plan
1. [Step-by-step actions]
```

## CLI Reference

```bash
# List all checks
arcanum-cli.sh checks PR_ID

# Filter checks
arcanum-cli.sh checks PR_ID --failed
arcanum-cli.sh checks PR_ID --active    # failed + pending
arcanum-cli.sh checks PR_ID --json       # raw JSON output

# Check details with CI launch status
arcanum-cli.sh check-log PR_ID "check type substring"

# List Sandbox tasks (CI jobs) for a check
arcanum-cli.sh ci-jobs PR_ID "check type substring"

# Smart error analysis (preferred — parses format/test/build errors)
sandbox-cli.sh errors TASK_ID
sandbox-cli.sh failed PR_ID              # analyze ALL failed tasks for PR

# Raw logs from Sandbox task
sandbox-cli.sh log TASK_ID               # execution_error.log + error grep
sandbox-cli.sh log TASK_ID execution.log # full execution log (tail 100)

# Search full execution.log for pattern (when errors command misses something)
sandbox-cli.sh search-log TASK_ID "pattern" [context_lines]

# Access task artifacts
sandbox-cli.sh artifact TASK_ID [TYPE] [FILE]

# Open review issues
arcanum-cli.sh open-issues PR_ID

# Close resolved issue
arcanum-cli.sh close-issue COMMENT_ID

# PR metadata
arcanum-cli.sh pr-data PR_ID

# Worktree management
arcanum-cli.sh worktree-create PR_ID [PATH]    # mount worktree for PR branch (fetches branch from PR metadata)
arcanum-cli.sh worktree-create NAME [PATH]     # mount worktree with new branch from trunk
arcanum-cli.sh worktree-remove PATH            # unmount and remove worktree
arcanum-cli.sh worktree-list                   # list all arc mounts
```

## Auth Requirements

- **Arcanum API**: arc token (`~/.arc/token` or `arc token show`)
- **CI Public API + Sandbox API**: CI token with `ci:api` scope (`~/.ci/token`)
  - Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=92335dd01cb64811bd913f7164f30594

## Sandbox Task Structure

CI tasks in Sandbox have:
- **Tags**: `CI`, `ACTION:<action-id>`, `JOB-ID:<job-id>`, `PATH:<dir>`
- **Input params**: `branch`, `commit`, `name` (format: `dir::action:job`)
- **Resources**:
  - `TASK_LOGS` — directory with log files:
    - `execution_error.log` — stderr (errors/warnings)
    - `execution.log` — full execution log
    - `common.log` — CI framework log
  - `TEAMCITY_ARTIFACTS` — build artifacts (Runner.log, .ipa, etc.)
