---
name: guru-route
description: Single CI entry point for Tracker-driven work. Loads the issue by key, classifies intent, selects rules and skills, runs the chosen workflow, and posts a Tracker update consistent with that workflow.
---

Use this skill when a run starts from a Tracker issue key (or id) and the right downstream workflow is not chosen in advance — planning, execution, DMP domain work, or incident investigation.

Hard rules:
- use Tracker MCP for issue facts and comments; use `arc` instead of `git` for any VCS lookup
- do not skip classification: always form an explicit request type before picking a skill
- after routing, obey the selected skill end to end (including its Tracker and language rules)
- **publish the outcome on the source issue**: the result of the run must appear as a **comment on the same Tracker issue** that was opened by key in step 1 (the original ticket). If the downstream skill already posts the full outcome there (plan comment, incident report, etc.), that comment counts; otherwise add a closing comment with the summary, links (PR, diffs), and verification. Do not finish the run with only a chat reply and no issue comment.
- **PR when execution is routed (`guru-code` / auto-exec)**: If classification selects the implementation skill (`guru-code`), opening a **pull request** is part of completing the workflow, not an optional follow-up. Follow `guru-code` literally: commit, then `arc pr create` (or the exact reason PR creation could not complete, per that skill). Do **not** stop after a local commit or chat summary without a PR link in the Tracker comment and in the final operator response — agents often forget this unless it is stated here.

All human-facing text for Tracker and the final user reply must be **in Russian**, unless a selected skill explicitly requires another language for a specific artifact.

## Pipeline

1. **Analyze the ticket by key**
   - extract issue key or id from the prompt
   - call `tracker_get_issue` and `tracker_get_issue_comments`
   - pull linked resources, changelog, or attachments when they change classification or scope
   - treat recent human comments as stronger than stale description text

2. **Classify the request**
   - pick **one primary** type (if two apply, choose the one that matches the latest comment or blocks the other; if still ambiguous, post a short clarification question in Tracker or default to planning-before-code for delivery work)
   - record the label internally (e.g. in a short preamble before acting) so the run stays consistent

3. **Find rules and skills**
   - **Rules**: apply workspace rules that match the repo area (e.g. DMP ETL presets, shared rule packs under `dmp/common/**/*` in artifacts, project-specific Cursor rules) when the classified work touches code, configs, or DMP operations
   - **Skills**: map the primary type to exactly one **primary** skill using the table below; read that skill’s `SKILL.md` (and `command.md` if referenced) before executing
   - if the ticket clearly needs a **sequence** (e.g. plan comment exists and the user wants implementation next), run skills **in order**, without merging their Tracker contracts into one ad-hoc format

4. **Apply the skill(s)**
   - follow the primary skill’s steps literally (subagents, todos, MCP tools, plan/PR flows) as that skill defines
   - when the primary skill is **`guru-code`**, treat **PR creation** as mandatory closure alongside commit; verify the PR exists (or the skill’s documented exception) before moving to Tracker reporting
   - do not substitute another workflow’s conventions

5. **Report in Tracker**
   - post to the **original issue** (same key as in step 1). The user-facing outcome lives in the issue thread, not only in the agent chat.
   - the Tracker update must match **both** the classified request type and the **skill that actually produced the outcome**:
     - plan-only / autonomous plan → follow `guru-plan` (plan comment structure, edit vs create, summonees)
     - code / PR / autonomous execution → follow `guru-code`; **still** ensure a result comment exists on the issue (the skill’s optional block becomes mandatory under this router); the comment **must** include the **PR link** (or the documented reason PR was not created) — not only commit hash
     - DMP incident / failure investigation → follow `guru-debug-accident` and its `command.md` report template
     - DMP Q&A → follow `guru-ask`
     - create table / task → follow `guru-create-table` or `guru-create-task` and its `command.md`
   - if multiple skills ran, either one consolidated comment that still respects each skill’s required sections, or separate comments in execution order — prefer what the **last** skill expects when it defines closure

## Classification → primary skill (reference)

| Request shape (examples) | Primary skill |
|--------------------------|---------------|
| Need an autonomous execution plan, no code yet | `guru-plan` |
| Implement, branch, commit, PR | `guru-code` |
| How dmp_suite / DWH works; docs-backed explanation | `guru-ask` |
| Failed task run, accident, root cause, incident ticket | `guru-debug-accident` |
| New ETL table workflow | `guru-create-table` |
| New ETL task workflow | `guru-create-task` |
| Nile → YQL transfilter migration in microbatch_from_hist | `guru-break-nile-2-yql` |

Extend this table when new skills appear: classify first, then map.

## Final response to the operator

Include: issue key, chosen request type, primary skill(s) used, **id or permalink of the Tracker comment(s)** that carry the published outcome on the source issue, and pointers to PR/plan links if applicable. If posting failed after retries, state that explicitly and why.
