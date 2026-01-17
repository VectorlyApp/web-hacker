# input_text Operation

> Type text into form fields (text inputs, password fields, textareas, search boxes). Auto-validates visibility to avoid honeypot inputs. Supports clearing existing text before typing. Use for filling out login forms, search queries, and data entry.

Type text into an input element (text field, textarea, etc.).

## Basic Format

```json
{
  "type": "input_text",
  "selector": "input[name='username']",
  "text": "{{username}}",
  "clear": false,
  "timeout_ms": 20000
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"input_text"` |
| `selector` | string | Yes | - | CSS selector for input element |
| `text` | string | Yes | - | Text to type |
| `clear` | bool | No | `false` | Clear existing text before typing |
| `timeout_ms` | int | No | `20000` | Max wait time for element (milliseconds) |

## Automatic Visibility Validation

Like `click`, this operation **validates element visibility** to avoid:
- Typing into hidden honeypot inputs (bot traps)
- Typing into invisible form fields

Only visible, interactable input elements will receive text.

## Using Placeholders

Both selector and text support placeholders:
```json
{
  "type": "input_text",
  "selector": "input[name='{{field_name}}']",
  "text": "{{field_value}}"
}
```

## Examples

### Simple Text Input
```json
{
  "type": "input_text",
  "selector": "input[name='email']",
  "text": "{{email}}"
}
```

### Password Field
```json
{
  "type": "input_text",
  "selector": "input[type='password']",
  "text": "{{password}}"
}
```

### Search Box
```json
{
  "type": "input_text",
  "selector": "input[placeholder='Search...']",
  "text": "{{search_query}}"
}
```

### Textarea
```json
{
  "type": "input_text",
  "selector": "textarea#comments",
  "text": "{{comment_text}}"
}
```

### Clear and Replace
```json
{
  "type": "input_text",
  "selector": "input#amount",
  "text": "{{new_amount}}",
  "clear": true
}
```

### Input by Label
```json
{
  "type": "input_text",
  "selector": "input[aria-label='Phone number']",
  "text": "{{phone}}"
}
```

## How It Works

1. **Find element** - Locates input using CSS selector
2. **Validate visibility** - Checks element is visible and interactable
3. **Focus element** - Prepares element for input
4. **Clear (optional)** - If `clear: true`, clears existing content
5. **Type characters** - Sends keydown/keyup events for each character via CDP
6. **Small delays** - 20ms between characters for realistic typing

## Metadata Captured

After execution, operation metadata includes:
- `selector`: The resolved selector
- `text_length`: Number of characters typed
- `element`: Element properties

## Common Input Selectors

| Pattern | Example | Description |
|---------|---------|-------------|
| `input[name='x']` | `input[name='email']` | By name attribute |
| `input[type='x']` | `input[type='text']` | By input type |
| `input#id` | `input#username` | By ID |
| `input[placeholder='x']` | `input[placeholder='Search']` | By placeholder |
| `textarea` | `textarea.comment` | Textarea elements |
| `[contenteditable]` | `div[contenteditable]` | Editable divs |

## Input Types That Work

- `text`
- `password`
- `email`
- `tel`
- `number`
- `search`
- `url`
- `textarea`

## Typical Form Flow

```json
[
  {
    "type": "navigate",
    "url": "https://example.com/login"
  },
  {
    "type": "input_text",
    "selector": "input[name='username']",
    "text": "{{username}}"
  },
  {
    "type": "input_text",
    "selector": "input[name='password']",
    "text": "{{password}}"
  },
  {
    "type": "click",
    "selector": "button[type='submit']"
  }
]
```

## Tips

1. **Use clear for edits** - When updating existing values, set `clear: true`
2. **Check for autocomplete** - Some sites have autocomplete that may interfere
3. **Input events** - The operation triggers proper input events that reactive frameworks detect
4. **Focus handling** - Element is automatically focused before typing
5. **Special characters** - All characters including special symbols are supported

## Error Cases

- **Element not found** - Throws error if selector doesn't match
- **Element not input** - Works best with actual input/textarea elements
- **Element hidden** - Throws error if element is not visible
- **Element disabled** - May fail on disabled inputs
