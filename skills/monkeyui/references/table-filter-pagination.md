# Pattern: Table with Filter and Pagination (load more)

Main pattern for list pages. Source: `/junk/ktnglazachev/vscode-ctr/schemes/pages/llm-recomendations/`

## Key Rules

- **One Query** for initial loading and loadMore — DO NOT create two separate ones
- `updateStrategy` merges data pages
- `reset: true` — for reset when filter changes
- `canLoad: !!next?.items?.length` — check via length, not through other fields
- `Filter` with `submitOnMount` automatically makes the first request when the page loads
- `Filter` automatically synchronizes values with URL — no need to do it manually

## Typical Errors

### Filter spec: no type `'select'` — use `'enum'`
```tsx
// ❌ Incorrect — type 'select' does not exist
spec={{ status: { type: 'select', options: [...] } }}

// ✅ Correct — use 'enum' for dropdown
spec={{ status: { label: 'Status', type: 'enum', options: [{ value: 'active', label: 'Active' }] } }}
```
Valid types: `'string' | 'number' | 'boolean' | 'password' | 'longtext' | 'enum' | 'collection' | 'date' | 'date-range' | 'ticket' | 'intranet'`

### onLoadMore: don't pass Query directly — use object form
```tsx
// ❌ Incorrect
onLoadMore={$queries.loadItems}

// ✅ Correct — object form with debounce
onLoadMore={{ fn: $queries.loadItems, debounce: 300 }}
```

### updateStrategy: non-null assertion for required response fields
```typescript
// ❌ Incorrect — TS complains: 'Meta | undefined' not assignable to 'Meta'
return { meta: next?.meta, ... };

// ✅ Correct — use ! if the field is guaranteed to be in the response
return { meta: next?.meta!, ... };
