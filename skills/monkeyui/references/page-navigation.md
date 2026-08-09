# Page Navigation Pattern

```tsx
// render.scheme.tsx — navigation between project pages

<Button onClick={() => $url.navigate('./pages/other-page', { query: { id: 1 }, target: '_self' })}>
    To another page
</Button>

{/* Embedding a page as a widget */}
<Include
    name="inner"
    link={$url.pageLink('./pages/inner-content')}
    variant="widget"
    hideTitle
/>