---
name: monkeyui
description: >
  Create UI on Monkeyui
  Use this skill when the user asks to do something using monkeyui.
  For example, creating a project, creating and editing a page,
  Also use this skill when working with files api.scheme.ts, queries.scheme.ts, render.scheme.tsx, uiconfig.json
---

# Creating a page on MonkeyUI

## What this skill can do

- Create a new MonkeyUI project (if `uiconfig.json` doesn't exist yet)
- Create a new page in an existing project
- Implement a specific UI scenario: table with filter, CRUD with sidebar, form, etc.

## Execution algorithm

### Step 1. Study the documentation and references

Before writing code, it is MANDATORY:
1. Read references from `ai/artifacts/skills/monkeyui/references/` - there are ready-made patterns:
   - `table-filter-pagination.md` - table with filter and pagination (load more and pagination)
   - `crud-sidebar.md` - CRUD with sidebar, view/edit modes, create/edit, row selection
   - `form-page.md` - all form controls, field relationships, Form+JSONEditor synchronization
   - `api-patterns.md` - API configuration (ABK, cookie, open-api-auto, manual), method naming
   - `project-structure.md` - uiconfig.json, file structure, types.scheme.d.ts
   - `modals-patterns.md` - multiple modals
   - `permission.md` - about permissions for controls or action
   - `page-navigation.md` - build link to other monkeyui page
2. For each component you plan to use, find its stories:
   `/taxi/frontend/services/ui-constructor/packages/storybook/src/stories/widgets/<ComponentName>.stories.tsx`
3. Reference page example (highest priority): `/junk/ktnglazachev/vscode-ctr/schemes/pages/llm-recomendations/`
4. Other examples:
   - Project `/junk/twin/pizza-nebula-ui/`,
   - Examples of using different components `/junk/ktnglazachev/vscode-ctr/schemes/pages/`
5. Study the rules: `/ai/artifacts/rules/techplatform/frontend/monkeyui/*.mdc`

### Step 2. Check for project existence

If `uiconfig.json` is missing, there is no project. Project creation methods by priority:
- If MCP server monkeyui is available, call the project creation command
- Ask the user to execute the command in vscode `Monkey UI: Init project`
- Create the project file structure manually based on references

### Step 3. Write schemas (in order: api → queries → render)

**api.scheme.ts:**
- If ABK: host `${$env.vars.abkHost}/<serviceName>`, `authorization: $env.vars.abkAuth`, `csrf: true`
- If ridetech feature: `authorization: 'cookie'`, `csrf: true`
- Prefer `open-api-auto` (generates types automatically)
- Make sure the path to the YAML file exists in arcadia

**queries.scheme.ts:**
- For lists with pagination - use `updateStrategy` (one Query for initial loading and loadMore)
- Read URL via `$url.query.get('param')`, not `$store.url.query`
- API response types are taken from the `$API` namespace

**render.scheme.tsx:**
- Read URL via `$store.url.query.param` (reactive subscription)
- Write to URL via `$url.query.update({})` / `$url.query.delete([])`
- Modal/sidebar: visibility via URL parameter
- Extract large blocks into `new Component(...)`

### Step 4. Compile and fix errors

Run in the project root (background process):
```bash
ya tool tpf mui compile project -w -t -e development -s "pages/<page name>" &> compilation_log;
```

Fix errors in order: api → queries → render.

If an error repeats more than 3 times:
1. Add `// @ts-nocheck` to all page files
2. Remove one by one from api > queries > render and fix errors

### Step 5. Final check

- [ ] No `@ts-nocheck` in files
- [ ] No type errors in `compilation_log`
- [ ] All logic in `queries`, not in `render`
- [ ] All components from documentation (not made up)
- [ ] Delete `compilation_log`, stop the background compilation process
- [ ] Run page preview (via MCP monkeyui or ask the user to call the vscode command `Monkey UI: Preview page`)