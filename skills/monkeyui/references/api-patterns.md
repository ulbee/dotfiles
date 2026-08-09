# Pattern: API Configuration (api.scheme.ts)

## Key Rules

- No `import` — everything is global
- Only `export const name = new API(...)`
- Prefer `open-api-auto` — it generates typing automatically
- Path to YAML — absolute from arcadia root, file must exist (check via search)
- If `features: ["ridetech"]` in uiconfig.json → mandatory `authorization: 'cookie'` and `csrf: true`

## ABK (Admin without code) / ridetech feature

Used for Yandex-team interfaces.

```typescript
// api.scheme.ts — ABK and if in uiconfig.json features contains "ridetech"

export const myService = new API({
    // serviceName is taken from the path to YAML after "/services/"
    // For example, for /taxi/backend-py3/services/corp-requests/... → serviceName = "corp-requests"
    host: `${$env.vars.abkHost}/corp-requests`,
    authorization: $env.vars.abkAuth,
    csrf: true,
    endpoints: {
        type: 'open-api-auto',
        source: '/taxi/backend-py3/services/corp-requests/docs/yaml/api/client_requests.yaml',
    },
});
```

## Multiple APIs on one page

```typescript
// api.scheme.ts — different services/hosts

export const services = new API({
    host: $env.vars.uplatformApiBaseURL,
    authorization: $env.vars.abkAuth,
    csrf: true,
    endpoints: {
        type: 'open-api-auto',
        source: '/taxi/schemas/schemas/services/uplatform-catalog/api/services.yaml',
    },
});

export const projects = new API({
    host: $env.vars.uplatformApiBaseURL,
    authorization: $env.vars.abkAuth,
    csrf: true,
    endpoints: {
        type: 'open-api-auto',
        source: '/taxi/schemas/schemas/services/uplatform-catalog/api/projects.yaml',
    },
});
```

## Manual API description (manual) — only if there is no YAML

```typescript
// api.scheme.ts — manual, when there is no openapi schema

export const entity = new API({
    host: `http://my-service.yandex-team.ru`,
    authorization: 'cookie',
    endpoints: {
        type: 'manual',
        source: {
            getList: {
                method: 'GET',
                url: '/api/v1/items',
            },
            getById: {
                method: 'GET',
                url: '/api/v1/items/:id',  // :id — URL parameter
            },
            create: {
                method: 'POST',
                url: '/api/v1/items',
            },
            update: {
                method: 'PATCH',
                url: '/api/v1/items/:id',
            },
            delete: {
                method: 'DELETE',
                url: '/api/v1/items/:id',
            },
        },
    },
});
```

## How to call API methods in queries

Method name is built from the path in YAML:
- HTTP method + path → camelCase
- For example: `GET /v1/items/search` → `getV1ItemsSearch`
- `POST /api/v1/client-requests/search` → `postApiV1ClientRequestsSearch`

```typescript
// queries.scheme.ts

// GET /v1/items → getV1Items
const result = await $api.myService.getV1Items({
    query: { limit: 20, offset: 0 },
});

// POST /v1/items → postV1Items
const created = await $api.myService.postV1Items({
    body: { name: 'test' },
});

// GET /v1/items/:id → getV1ItemsId (or with urlParams)
const item = await $api.myService.getV1ItemsId({
    urlParams: { id: '123' },
});

// PATCH /v1/items/:id → patchV1ItemsId
await $api.myService.patchV1ItemsId({
    urlParams: { id: '123' },
    body: { name: 'updated' },
});

// DELETE /v1/items/:id → deleteV1ItemsId
await $api.myService.deleteV1ItemsId({
    urlParams: { id: '123' },
});

// Mixed parameters
const response = await $api.myService.postApiV1Search({
    query: { limit: 50 },   // URL query params
    body: { filter: {} },   // Request body
});

// URL params + query + body
await $api.myService.putV1Filter({
    urlParams: { filterId: '123' },
    query: { filter_id: '123' },
    body: { ...fields },
});

// Headers
await $api.myService.putV1Filter({
    headers: { 'X-Filter-ID': '123' },
    query: { filter_id: '123' }
});
```

## API Response Types

```typescript
// queries.scheme.ts — types from $API namespace (autogeneration)

// Namespace is built from the API variable name (first letter capitalized)
// export const myService → $API.MyService

const item: $API.MyService.GetV1ItemsResponse = await $api.myService.getV1Items();

// Type of a specific field
const items: $API.MyService.GetV1ItemsResponse['items'] = result.items;
