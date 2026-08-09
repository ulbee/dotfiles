---
name: ast-index
description: >
  This skill should be used when the user asks to "find a class", "search for symbol",
  "find usages", "find implementations", "search codebase", "find file",
  "class hierarchy", "find callers", "module dependencies", "unused dependencies",
  "project map", "project conventions", "project structure", "what frameworks",
  "what architecture", "find Kotlin class", "find Swift protocol", "find Python class",
  "Go struct", "Go interface", "find React component", "find TypeScript interface",
  "find Rust struct", "find Ruby class", "find C# controller", "find Dart class",
  "find PHP class", "find Perl subs", "Perl exports", "outline file",
  or needs fast code search in any supported language project.
  Also triggered by mentions of "ast-index" CLI tool.
user-invocable: false
---

# ast-index — Fast Code Search

Native Rust CLI for structural code search across 30 programming languages using SQLite + FTS5 index. Available via `ya tool ast-index`.

## Critical Rules

**ALWAYS use ast-index FIRST for any code search task.**

1. **ast-index is the PRIMARY search tool** — use it before grep, ripgrep, or Search tool
2. **DO NOT duplicate results** — if ast-index found usages/implementations, that IS the complete answer
3. **DO NOT run grep "for completeness"** after ast-index returns results
4. **Use grep/Search ONLY when:** ast-index returns empty results, searching for regex patterns, string literals, or comment content

**Why:** 17-69x faster than grep (1-10ms vs 200ms-3s), structured and accurate results.

## Install & Initialize

```bash
ya tool ast-index version          # Verify installation
ya tool ast-index --help           # Show all commands
ya tool ast-index <command> --help # Help for specific command
ya tool ast-index rebuild          # Full index build
ya tool ast-index rebuild -j 32    # Use 32 threads (recommended for Arcadia VFS)
ya tool ast-index update           # Incremental update (changed files only)
```

Index stored at `~/.cache/ast-index/<project-hash>/index.db`.

**Important for Arcadia:** Always use `-j 32` (or higher) when rebuilding in arc-mounted repos — VFS has high per-file latency, parallelism compensates for it.

## Core Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `search` | Universal search across files, symbols, modules | `search "Payment"` |
| `file` | Find files by name | `file "Fragment.kt"` |
| `symbol` | Find symbols by name | `symbol "PaymentInteractor"` |
| `class` | Find class/interface definitions | `class "BaseFragment"` |
| `usages` | Find all symbol usages | `usages "PaymentRepository"` |
| `refs` | Cross-references (defs + imports + usages) | `refs "BaseFragment"` |
| `implementations` | Find all implementations of class/interface | `implementations "Repository"` |
| `hierarchy` | Display class inheritance tree | `hierarchy "BaseFragment"` |
| `callers` | Find function call sites | `callers "onClick"` |
| `call-tree` | Show call hierarchy (who calls callers) | `call-tree "processPayment" --depth 3` |
| `outline` | Show all symbols in a file | `outline "File.kt"` |
| `imports` | List imports in a file | `imports "File.kt"` |
| `todo` | Find TODO/FIXME comments | `todo` |
| `deprecated` | Find @Deprecated items | `deprecated` |
| `unused-symbols` | Find potentially unused symbols | `unused-symbols --module path/` |
| `changed` | Symbols changed in VCS diff | `changed --base trunk` |
| `map` | Project overview with symbol counts | `map` |
| `conventions` | Auto-detect architecture patterns | `conventions` |
| `api` | Show public API of a module | `api "path/to/module"` |
| `module` | Find modules by name | `module "payments"` |
| `deps` | Module dependencies | `deps "module-name"` |
| `dependents` | Reverse module dependencies | `dependents "module-name"` |
| `unused-deps` | Find unused module dependencies | `unused-deps "module-name"` |
| `agrep` | Structural AST search (requires ast-grep) | `agrep "class $N : Base($$$)" --lang kotlin` |
| `query` | Raw SQL against index DB | `query "SELECT ..."` |
| `schema` | Show DB tables and columns | `schema` |
| `db-path` | Print SQLite DB file path | `db-path` |
| `stats` | Show index statistics | `stats` |
| `clear` | Delete index for current project | `clear` |
| `watch` | Auto-update index on file changes | `watch` |
| `add-root` | Add additional source root | `add-root /path` |
| `remove-root` | Remove source root | `remove-root /path` |
| `list-roots` | List configured source roots | `list-roots` |
| `annotations` | Find classes with annotation | `annotations "@Service"` |
| `provides` | Find @Provides/@Binds (Dagger) | `provides "UserRepo"` |
| `inject` | Find @Inject points | `inject "NetworkModule"` |
| `composables` | Find @Composable functions | `composables` |
| `suspend` | Find suspend functions | `suspend` |
| `flows` | Find Flow/StateFlow/SharedFlow | `flows` |
| `extensions` | Find extension functions | `extensions` |
| `deeplinks` | Find deeplinks | `deeplinks` |
| `previews` | Find @Preview functions | `previews` |
| `suppress` | Find @Suppress annotations | `suppress` |
| `xml-usages` | Find class usages in XML layouts | `xml-usages "ClassName"` |
| `resource-usages` | Find resource usages | `resource-usages "ic_icon"` |
| `storyboard-usages` | Find class in storyboards/XIBs | `storyboard-usages "ClassName"` |
| `asset-usages` | Find iOS asset usages | `asset-usages "iconName"` |
| `swiftui` | Find SwiftUI views | `swiftui` |
| `async-funcs` | Find async functions (Swift) | `async-funcs` |
| `publishers` | Find Combine publishers | `publishers` |
| `main-actor` | Find @MainActor annotations | `main-actor` |
| `perl-exports` | Find exported Perl symbols | `perl-exports "Module"` |
| `perl-subs` | Find Perl subroutines | `perl-subs "Module"` |
| `perl-pod` | Find POD documentation | `perl-pod "Module"` |
| `perl-imports` | Find use/require statements | `perl-imports "file.pm"` |
| `perl-tests` | Find test assertions | `perl-tests` |
| `version` | Show CLI version | `version` |
| `--help` | Show all commands or help for a command | `--help`, `search --help` |

All commands invoked as `ya tool ast-index <command>`.

## Common Flags

| Flag | Description |
|------|-------------|
| `--fuzzy` | Fuzzy search: exact → prefix → contains |
| `--in-file <PATH>` | Filter by file path (substring) |
| `--module <PATH>` | Filter by module path |
| `--limit <N>` | Max results |
| `--format json` | JSON output |

## Platform-Specific Commands

### Android/Kotlin/Java/Spring

`provides`, `inject`, `composables`, `previews`, `suspend`, `flows`, `extensions`, `deeplinks`, `xml-usages`, `resource-usages`, `annotations`, `suppress`

For details: **`references/platform-commands.md`**

### iOS/Swift/ObjC

`storyboard-usages`, `asset-usages`, `swiftui`, `async-funcs`, `main-actor`, `publishers`

### Perl

`perl-exports`, `perl-subs`, `perl-pod`, `perl-imports`, `perl-tests`

## Index Management

```bash
ya tool ast-index rebuild                  # Full rebuild
ya tool ast-index rebuild --no-deps        # Skip module dependencies
ya tool ast-index rebuild --no-ignore      # Include gitignored files
ya tool ast-index rebuild --sub-projects   # Index sub-projects separately
ya tool ast-index update                   # Incremental update
ya tool ast-index clear                    # Delete index
ya tool ast-index watch                    # Auto-update on file changes
ya tool ast-index stats                    # Index statistics
```

## Multi-Root Projects

```bash
ya tool ast-index add-root /path/to/other   # Add source root
ya tool ast-index remove-root /path/to/other
ya tool ast-index list-roots
```

## Workflow

1. `ya tool ast-index rebuild` — once per project
2. `ya tool ast-index conventions` + `ya tool ast-index map` — understand structure (~80 lines)
3. `ya tool ast-index map --module <path>` — drill into specific areas
4. `ya tool ast-index search` / `class` / `symbol` — find code
5. `ya tool ast-index usages` / `callers` — understand usage before refactoring
6. `ya tool ast-index changed --base trunk` — before code review
7. `ya tool ast-index update` — keep index fresh

## Supported Languages

Kotlin, Java, Swift, Objective-C, TypeScript, JavaScript, Vue, Svelte, Rust, Ruby, C#, Python, Go, C++, Scala, PHP, Dart, Perl, Lua, Elixir, Bash, SQL, R, Matlab, Groovy, Common Lisp, GDScript, BSL, Protocol Buffers, WSDL/XSD.

## Additional Resources

### Reference Files

For detailed information, consult:

- **`references/platform-commands.md`** — Android, iOS, Perl, TypeScript platform-specific commands with examples
- **`references/sql-and-schema.md`** — Database schema, raw SQL queries, direct DB access examples
- **`references/structural-search.md`** — ast-grep patterns, agrep usage examples
