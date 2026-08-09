# SQL Queries & Database Schema

## Raw SQL Query

Execute any SELECT query against the index database (JSON output):

```bash
# Find all classes
ya tool ast-index query "SELECT s.name, s.kind, f.path FROM symbols s JOIN files f ON s.file_id = f.id WHERE s.kind = 'class'"

# Find classes implementing an interface with no usages
ya tool ast-index query "SELECT s.name, f.path FROM symbols s JOIN files f ON s.file_id = f.id JOIN inheritance i ON s.id = i.child_id WHERE i.parent_name = 'Repository' AND s.name NOT IN (SELECT name FROM refs)"

# Complexity hotspots — files with most symbols
ya tool ast-index query "SELECT f.path, COUNT(*) as sym_count FROM symbols s JOIN files f ON s.file_id = f.id GROUP BY f.id ORDER BY sym_count DESC LIMIT 20"

# Module dependency analysis
ya tool ast-index query "SELECT m.name, COUNT(*) as dep_count FROM module_deps md JOIN modules m ON md.module_id = m.id GROUP BY m.id ORDER BY dep_count DESC"

# CTE — transitive dependency chain
ya tool ast-index query "WITH RECURSIVE chain AS (SELECT md.dep_module_id, m.name, 1 as depth FROM module_deps md JOIN modules m ON md.dep_module_id = m.id WHERE md.module_id = (SELECT id FROM modules WHERE name LIKE '%payments%') UNION ALL SELECT md.dep_module_id, m.name, c.depth + 1 FROM chain c JOIN module_deps md ON md.module_id = c.dep_module_id JOIN modules m ON md.dep_module_id = m.id WHERE c.depth < 5) SELECT DISTINCT name, depth FROM chain ORDER BY depth, name"
```

**Security**: Only SELECT, WITH, and EXPLAIN queries allowed. Mutations blocked.

## Database Schema

```bash
ya tool ast-index schema    # Show all tables with columns and row counts
ya tool ast-index db-path   # Get SQLite DB path for external tools
```

### Key Tables

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `files` | Indexed source files | `path`, `mtime`, `size` |
| `symbols` | Classes, functions, properties | `name`, `kind`, `line`, `file_id`, `signature` |
| `symbols_fts` | FTS5 full-text search | `name`, `signature` |
| `inheritance` | Parent-child type relationships | `child_id`, `parent_name`, `kind` |
| `refs` | Symbol references/usages | `name`, `line`, `file_id`, `context` |
| `modules` | Build modules (Gradle, Maven) | `name`, `path`, `kind` |
| `module_deps` | Module → module dependencies | `module_id`, `dep_module_id` |
| `transitive_deps` | Pre-computed transitive deps | `module_id`, `dependency_id`, `depth` |
| `xml_usages` | Android XML layout class usages | `class_name`, `file_path` |
| `resources` | Android resource definitions | `type`, `name`, `file_path` |

### Direct Database Access

```python
import sqlite3, subprocess
db_path = subprocess.check_output(["ya", "tool", "ast-index", "db-path"]).decode().strip()
conn = sqlite3.connect(db_path)

unused_impls = conn.execute("""
    SELECT s.name, f.path, i.parent_name
    FROM symbols s
    JOIN files f ON s.file_id = f.id
    JOIN inheritance i ON s.id = i.child_id
    WHERE s.name NOT IN (SELECT name FROM refs)
    ORDER BY i.parent_name, s.name
""").fetchall()
```

**When to use `query` vs predefined commands:**
- Simple lookups → use `search`, `class`, `usages` (faster, formatted)
- Complex joins, aggregation, negative conditions → use `query`
- Batch analysis, scripting, CI → use `db-path` + direct SQLite
