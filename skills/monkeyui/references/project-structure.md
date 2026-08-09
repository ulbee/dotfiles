# Project Structure and uiconfig.json

## File Structure

```
<project-root>/
├── uiconfig.json          # project config (required)
├── a.yaml                 # CI pipeline (do not touch)
└── pages/
    └── <page-name>/
        ├── api.scheme.ts       # API endpoint declaration
        ├── queries.scheme.ts   # business logic and queries
        ├── render.scheme.tsx   # UI markup (JSX)
        ├── types.scheme.d.ts   # helper types (optional)
        └── tsconfig.json       # service file (do not touch)
```

## uiconfig.json — regular project (cookie authorization)

```json
{
    "name": "my-project-name",
    "workspace": [
        "pages/*"
    ],
    "features": [],
    "envs": {
        "default": {
            "myApiHost": "https://my-service.tst.yandex-team.ru"
        },
        "production": {
            "myApiHost": "https://my-service.yandex-team.ru"
        }
    },
    "domain": "yandex-team.ru"
}
```

## uiconfig.json — ridetech project (using abk)

If ridetech infrastructure is used: all APIs must have `authorization: 'cookie'` and `csrf: true`.

```json
{
    "name": "my-ridetech-project",
    "workspace": [
        "pages/*"
    ],
    "features": [
        "ridetech"
    ],
    "envs": {
        "default": {
            "apiHost": "https://my-service.taxi.tst.yandex-team.ru"
        },
        "production": {
            "apiHost": "https://my-service.taxi.yandex-team.ru"
        }
    },
    "domain": "yandex-team.ru"
}
```


> `abkHost` and `abkAuth` — built-in variables for ABK, no need to add them to envs

## types.scheme.d.ts

Used for typing URL parameters and custom types.

```typescript
// types.scheme.d.ts

declare global {
    // URL parameter typing — autocomplete in $store.url.query and $url.query
    interface UrlQuery {
        filter: Filter;
        itemId?: string;
        mode?: 'view' | 'edit' | 'create';
        page?: number;
    }
}

// Custom types (available via $Types.Filter etc.)
export type Filter = {
    search?: string;
    status?: string;
    dateFrom?: string;
    dateTo?: string;
}

export type SortConfig = {
    column: string;
    order: 'asc' | 'desc';
}
```

## Rules for types.scheme.d.ts

- No `import` — everything is global
- Only type, interface and namespace descriptions
- Do not describe API types — they are already in `$API`
- Use `$Types.TypeName` to refer to types
- Avoid `any`

## render.scheme.tsx — required structure

```tsx
// Optional Component-components (before export default)
const SomeBlock = new Component(() => (
    <Container>...</Container>
));

// Required export
export default new UI({
    tags: ['tag-name'],         // tags for catalog
    markup: (
        <Page title="Page Title">
            {/* content */}
        </Page>
    ),
});
```

## Page Tags

Tags are used for filtering in the catalog (`MainPage`/`filterCatalogue`):

```tsx
// render.scheme.tsx
export default new UI({
    tags: ['my-service'],  // arbitrary tag for catalog
    markup: (
        <Page title="...">...</Page>
    ),
});

// Catalog page — shows only pages with certain tags
export default new UI({
    tags: ['main'],
    markup: (
        <MainPage
            serviceName="My Service"
            filterCatalogue={(_, page) => page.tags.includes('my-service')}
        />
    ),
});
