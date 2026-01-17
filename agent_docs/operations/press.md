# press Operation

> Press keyboard keys (Enter, Tab, Escape, Arrow keys, etc.). Use for form submission without clicking, navigating autocomplete dropdowns, closing modals, and keyboard shortcuts.

Press a keyboard key. Useful for submitting forms, navigating, or triggering keyboard shortcuts.

## Basic Format

```json
{
  "type": "press",
  "key": "enter"
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"press"` |
| `key` | string | Yes | - | Key name to press |

## Supported Keys

| Key Name | Alternative | Description |
|----------|-------------|-------------|
| `enter` | - | Submit forms, confirm |
| `tab` | - | Move to next field |
| `escape` | `esc` | Cancel, close modals |
| `backspace` | - | Delete character before cursor |
| `delete` | - | Delete character after cursor |
| `arrowup` | - | Navigate up |
| `arrowdown` | - | Navigate down |
| `arrowleft` | - | Navigate left |
| `arrowright` | - | Navigate right |
| `home` | - | Jump to start |
| `end` | - | Jump to end |
| `pageup` | - | Scroll up a page |
| `pagedown` | - | Scroll down a page |
| `space` | - | Space character, toggle buttons |
| `shift` | - | Shift modifier |
| `control` | `ctrl` | Control modifier |
| `alt` | - | Alt modifier |
| `meta` | - | Cmd/Win key |

## Examples

### Submit Form with Enter
```json
[
  {
    "type": "input_text",
    "selector": "input[name='search']",
    "text": "{{query}}"
  },
  {
    "type": "press",
    "key": "enter"
  }
]
```

### Tab Through Form
```json
[
  {
    "type": "input_text",
    "selector": "input[name='first_name']",
    "text": "{{first_name}}"
  },
  {
    "type": "press",
    "key": "tab"
  },
  {
    "type": "input_text",
    "selector": "input[name='last_name']",
    "text": "{{last_name}}"
  }
]
```

### Close Modal
```json
{
  "type": "press",
  "key": "escape"
}
```

### Navigate Dropdown
```json
[
  {
    "type": "click",
    "selector": "select#country"
  },
  {
    "type": "press",
    "key": "arrowdown"
  },
  {
    "type": "press",
    "key": "arrowdown"
  },
  {
    "type": "press",
    "key": "enter"
  }
]
```

## How It Works

1. Sends `keyDown` event via CDP Input domain
2. Brief delay (52.5ms)
3. Sends `keyUp` event

## When to Use

- Submit forms without clicking button
- Navigate autocomplete suggestions
- Close modals/dialogs
- Trigger keyboard shortcuts
- Navigate select dropdowns

## Notes

- Key names are case-insensitive
- Single key press only (no key combinations yet)
- Focus must be on appropriate element for some keys to work
