# Eval cases for the arc skill

## What are eval cases

Eval cases verify that the skill correctly guides the model when working with arc CLI. Each case contains a user prompt and a set of expectations that allow objective assessment of the response.

Why this matters: arc looks like git but behaves differently. Unsupported flags silently produce empty or incorrect output. Eval cases capture these traps and ensure the skill does not degrade over time.

## evals.json structure

The `evals.json` file stores all cases in a single array:

```json
{
  "skill_name": "arc",
  "evals": [
    {
      "id": 1,
      "prompt": "Я в директории /repo/services/myservice/. Покажи какая сейчас ветка.",
      "expected_output": "Uses arc info --json and extracts the branch field, NOT arc branch --show-current",
      "files": [],
      "expectations": [
        "Uses arc info --json to get the current branch",
        "Does NOT use arc branch --show-current or git branch --show-current",
        "Extracts the branch field from JSON output"
      ],
      "covers": "scenario: check state (SKILL.md)"
    }
  ]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | number | Unique integer identifier |
| `prompt` | string | User request (in Russian, matching real usage). Simulates a real question |
| `expected_output` | string | Short description of correct behavior, for quick understanding |
| `files` | string[] | Input files if needed (paths relative to skill root) |
| `expectations` | string[] | Specific verifiable assertions, typically 2-5. Formulated as facts that can be confirmed or refuted |
| `covers` | string | (optional) Reference to the SKILL.md section or reference file this case covers |

### Writing good expectations

Good expectations are objectively verifiable. Each assertion can be unambiguously evaluated as true/false from the execution transcript.

Useful patterns:
- **Positive**: "Uses `arc diff -B` to get the diff"
- **Negative**: "Does NOT use `arc diff trunk...HEAD`" (catches a specific mistake)
- **Structural**: "Extracts the branch field from JSON output"
- **Warning**: "Warns about the double prefix users/ issue"

Bad expectations are subjective and vague ("Response is helpful", "Code is clean").

## Running eval cases

Eval cases are run via skill-creator. For each case, an executor agent receives the prompt with access to the skill, then a grader agent checks the expectations.

```
/skill-creator improve the arc skill, run eval cases
```

Results are saved to `arc-workspace/iteration-N/` and include:
- `grading.json` with pass/fail results for each expectation
- `timing.json` with duration and token counts
- `benchmark.json` with aggregate statistics
- HTML viewer for visual review

## When and how to update eval cases

### Changed information in the skill

When you update rules, commands, or the gotcha table in SKILL.md or reference files:

1. Find affected cases (the `covers` field helps with this)
2. Update `expectations` in affected cases to reflect the new behavior
3. Run eval cases and confirm the pass rate has not dropped

Example: you added a rule that `arc stash` does not support `--keep-index`. Find stash-related cases, add an expectation "Does NOT use `arc stash --keep-index`".

### Added a new scenario to the skill

When you add a new section to SKILL.md or a new reference file:

1. Write 2-3 cases covering the main path and edge cases
2. Use the next `id` after the last existing one
3. Fill in `covers` with a reference to the new section
4. Run the new cases alongside the old ones to verify the new instructions did not break existing behavior

### Caught a real case where the skill performs poorly

This is the most valuable source of new eval cases:

1. Capture the prompt and the incorrect behavior as-is
2. Formulate expectations that describe the correct behavior
3. Add the case to evals.json
4. Fix the skill (SKILL.md, reference files)
5. Run evals, confirm the new case passes and existing ones are not broken

Example: the model used `arc log -5` instead of `arc log -n 5`. Add a case with expectations "Does NOT use `arc log -5`" and "Uses `arc log -n 5`".

### Refactored the skill (restructuring, renaming files)

1. Update references in `covers` to reflect current paths and line numbers
2. Run all eval cases to verify the refactoring did not affect behavior
3. No need to change expectations if behavior has not changed

### Updated the skill description

The description affects triggering, not behavior. Eval cases in evals.json test behavior, so they don't need changes. To test triggering, use a separate trigger-eval set via skill-creator.

## Case organization

Current cases are grouped thematically:

| ID range | Topic |
|----------|-------|
| 1-6 | Basic commands (branch, diff, log, push, checkout) |
| 7-14 | PRs and commits |
| 15-24 | Code review and diff |
| 25-31 | Special cases (short hashes, submit, JSON parsing) |
| 32-36 | Commit history (revert, blame, search) |
| 37-43 | Advanced operations (rebase, cherry-pick, conflicts) |

When adding new cases, append them at the end with the next `id`. The thematic grouping by ID range is a loose convention, not a strict requirement.

## Checklist before committing

- [ ] All `id` values are unique
- [ ] Each case has at least 2 expectations
- [ ] Expectations are objectively verifiable (not subjective)
- [ ] File is valid JSON (`python3 -c "import json; json.load(open('evals.json'))"`)
- [ ] If the skill was changed, eval cases were run and results verified
