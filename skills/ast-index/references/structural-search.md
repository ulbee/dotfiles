# Structural Search (ast-grep)

Structural code search using AST patterns. Requires `sg` (ast-grep) installed.

## Usage

```bash
# Simple pattern matching
ya tool ast-index agrep "router.launch($$$)" --lang kotlin
ya tool ast-index agrep "@Inject constructor($$$)" --lang kotlin
ya tool ast-index agrep "suspend fun $NAME($$$)" --lang kotlin

# Find classes extending a specific base
ya tool ast-index agrep "class $NAME : BasePresenter($$$)" --lang kotlin

# Find async functions (Swift)
ya tool ast-index agrep "func $NAME($$$) async" --lang swift

# Find React components
ya tool ast-index agrep "export default function $NAME($$$)" --lang typescript

# JSON output
ya tool ast-index agrep "@Composable fun $NAME($$$)" --lang kotlin --json
```

## Pattern Syntax

- `$NAME` — matches a single AST node (captures as metavariable)
- `$$$` — matches zero or more AST nodes (variadic)
- Everything else is literal pattern matching against the AST

## When to Use

- `composables`, `inject`, `suspend` → use built-in commands (faster, pre-configured)
- Custom structural patterns, negative matching, context queries → use `agrep`
