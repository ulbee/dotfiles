# Access Rights (permission)

## Key Rules

When features: "ridetech" is present, `AuthProvider` is already used under the hood and does not need to be explicitly specified

## Examples

```tsx
// render.scheme.tsx — limiting features by rights

// Button is available only to users with permission
<Button variant="action" permission="items.edit">
    Edit
</Button>

// Page requires permission to view
<Page title="Management" permission={['items.view', 'items.manage']}>
    ...
</Page>

// Form — only for authenticated users
<Form permission="items.edit" onSubmit={$queries.save}>
    ...
</Form>

// AuthProvider — for pages with custom authorization
<AuthProvider
    onLoad={$queries.myApi.getAuthMe}
    login={$store.queries.myApi?.getAuthMe?.result?.login}
    permissions={$store.queries.myApi?.getAuthMe?.result?.permissions || []}
    loading={$store.queries.myApi?.getAuthMe?.isLoading}
>
    <Page title="Menu" permission={['pizzas.view']}>
        ...
    </Page>
</AuthProvider>