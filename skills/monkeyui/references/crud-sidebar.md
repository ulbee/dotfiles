# Pattern: CRUD with Sidebar

Pattern for pages with viewing/editing records in a sidebar panel.
Sources:
- `/junk/ktnglazachev/vscode-ctr/schemes/pages/llm-recomendations/`
- `/junk/twin/pizza-nebula-ui/pages/menu/`
- `/junk/ktnglazachev/vscode-ctr/schemes/pages/log-monitoring/`

## Key Rules

- Modal visibility is controlled via URL parameter (`itemId`, `mode`)
- Modal's `onLoad` is called when opening — use it to load details
- For modes (view/edit) use an additional URL parameter `mode`
- Closing — `$url.query.delete(['itemId', 'mode'])`
- Opening — `$url.query.update({ itemId: item.id, mode: 'view' })`
- Large Modal block is extracted to `new Component`
- `onRowClick` in Table opens the sidebar
