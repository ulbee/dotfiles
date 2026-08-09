# Pattern: Form Page

Sources:
- `/taxi/frontend/services/ui-constructor/packages/storybook/src/stories/widgets/Form.stories.tsx`
- `/taxi/frontend/services/ui-constructor/packages/storybook/src/stories/widgets/Filter.stories.tsx`
- `/junk/ktnglazachev/vscode-ctr/schemes/pages/form/`
- `/junk/ktnglazachev/vscode-ctr/schemes/pages/sync/`

## Key Rules

- `Form` accepts `onSubmit`, `initialValue`, `onChange`
- `Form` will catch a thrown error dictionary and show them next to the fields
- Field values inside `Form` are controlled via `value`/`checked`
- `Filter` — for search/filter fields (synchronizes with URL automatically)
- Relationship between fields — via `onChange` with `form.update({...})`
- Cannot use `async`/`await` and hooks in render
- Filter by default saves all form values to the address bar via `$url.query.update({[Filter.name]: {...other, [fieldName]: fieldValue})`,

## Available Controls

- Checkbox
- CodeEditor
- ColorPicker
- DateRange
- DateTime
- FileInput
- FormCollection
- RadioButton
- RadioGroup
- Select
- SelectIntranet
- SelectTicket
- Switch
- TextArea
- TextInput
- Timeline
- GeoPicker