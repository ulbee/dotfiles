# Modal Window Patterns

## Multiple Modal Windows

Source: `/junk/ktnglazachev/vscode-ctr/schemes/pages/modals/`

```tsx
// render.scheme.tsx — managing multiple modals through URL

export default new UI({
    markup: (
        <Page title="Modal Windows">
            <Container direction="vertical">
                <Button onClick={() => $url.query.update({ show: 'modal' })}>Open Modal</Button>
                <Button onClick={() => $url.query.update({ show: 'sidebar' })}>Open Sidebar</Button>
            </Container>

            {/* Regular modal */}
            <Modal
                title="Modal Window"
                visible={$store.url.query.show === 'modal'}
                onClose={() => $url.query.delete('show')}
            >
                <SimpleText>Content</SimpleText>
                <Modal.Actions>
                    <Button onClick={() => $url.query.update({ show2: 'inner' })}>
                        Open Nested Modal
                    </Button>
                    <Button onClick={() => $url.query.delete('show')}>Close</Button>
                </Modal.Actions>
            </Modal>

            {/* Sidebar */}
            <Modal
                title="Side Panel"
                visible={$store.url.query.show === 'sidebar'}
                onClose={() => $url.query.delete('show')}
                variant="sidebar"
            >
                <SimpleText>Sidebar Content</SimpleText>
                <Modal.Actions>
                    <Modal.CloseButton>Close</Modal.CloseButton>
                </Modal.Actions>
            </Modal>

            {/* Nested modal */}
            <Modal
                title="Nested"
                visible={$store.url.query.show2 === 'inner'}
                onClose={() => $url.query.delete('show2')}
            >
                <SimpleText>Nested Content</SimpleText>
                <Modal.Actions>
                    <Button onClick={() => $url.query.delete('show2')}>Close</Button>
                </Modal.Actions>
            </Modal>
        </Page>
    ),
});
```

## Modal Window via Query (Programmatic Control)

```typescript
// queries.scheme.ts — modal management through store, not URL

export const activeModal = new Query((modalId: string | null = null) => modalId);

export const openModal = new Query((id: string) => {
    $queries.activeModal(id);
});

export const closeModal = new Query(() => {
    $queries.activeModal(null);
});
```

```tsx
// render.scheme.tsx
<Modal
    title="Controlled Modal"
    visible={$store.queries.activeModal?.result === 'copy'}
    onClose={$queries.closeModal}
>
    ...
</Modal>