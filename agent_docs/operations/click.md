# click Operation

> Click buttons, links, and interactive elements by CSS selector. Auto-validates visibility to avoid honeypot traps. Supports left/right/middle click and double-click. Use for form submissions, navigation, opening modals, and triggering UI actions.

Click on an element in the page by CSS selector.

## Basic Format

```json
{
  "type": "click",
  "selector": "button.submit",
  "button": "left",
  "click_count": 1,
  "timeout_ms": 20000,
  "ensure_visible": true
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"click"` |
| `selector` | string | Yes | - | CSS selector for element to click |
| `button` | string | No | `"left"` | Mouse button: `"left"`, `"right"`, `"middle"` |
| `click_count` | int | No | `1` | Number of clicks (2 for double-click) |
| `timeout_ms` | int | No | `20000` | Max wait time for element (milliseconds) |
| `ensure_visible` | bool | No | `true` | Scroll element into view before clicking |

## Automatic Visibility Validation

The click operation **automatically validates element visibility** to avoid:
- Clicking hidden honeypot elements (bot traps)
- Clicking invisible overlays
- Clicking elements with `display: none` or `visibility: hidden`

Only visible, interactable elements will be clicked.

## Using Placeholders

Selectors can include placeholders:
```json
{
  "type": "click",
  "selector": "button[data-id='{{item_id}}']"
}
```

## Examples

### Click a Button
```json
{
  "type": "click",
  "selector": "button[type='submit']"
}
```

### Click Link by Text
```json
{
  "type": "click",
  "selector": "a:contains('Next Page')"
}
```
Note: `:contains()` is a jQuery-style selector - may not work in all contexts. Prefer attribute selectors.

### Click by ID
```json
{
  "type": "click",
  "selector": "#login-button"
}
```

### Click by Class
```json
{
  "type": "click",
  "selector": ".btn-primary"
}
```

### Double-Click
```json
{
  "type": "click",
  "selector": ".editable-cell",
  "click_count": 2
}
```

### Right-Click (Context Menu)
```json
{
  "type": "click",
  "selector": ".file-item",
  "button": "right"
}
```

### Click with Attribute Selector
```json
{
  "type": "click",
  "selector": "button[data-action='delete'][data-id='{{item_id}}']"
}
```

### Click nth Element
```json
{
  "type": "click",
  "selector": ".result-item:nth-child(1) .action-btn"
}
```

## How It Works

1. **Find element** - Locates element using CSS selector
2. **Validate visibility** - Checks element is visible and interactable
3. **Scroll into view** - If `ensure_visible: true`, scrolls element into viewport
4. **Get coordinates** - Calculates click position (element center)
5. **Dispatch click** - Sends mouse down/up events via CDP

## Metadata Captured

After execution, operation metadata includes:
- `selector`: The resolved selector
- `element`: Element properties (tag, classes, etc.)
- `click_coordinates`: `{x, y}` of where the click occurred

## Common Selectors

| Pattern | Example | Description |
|---------|---------|-------------|
| `#id` | `#submit-btn` | By ID |
| `.class` | `.btn-primary` | By class |
| `tag` | `button` | By tag name |
| `[attr]` | `[data-testid]` | Has attribute |
| `[attr='value']` | `[type='submit']` | Attribute equals |
| `[attr*='value']` | `[class*='btn']` | Attribute contains |
| `parent > child` | `form > button` | Direct child |
| `ancestor descendant` | `.form button` | Any descendant |
| `:first-child` | `li:first-child` | First child |
| `:nth-child(n)` | `tr:nth-child(2)` | Nth child |
| `:not(selector)` | `button:not(.disabled)` | Negation |

## Error Cases

- **Element not found** - Throws error if selector doesn't match any element
- **Element hidden** - Throws error if element is not visible
- **Timeout** - Throws error if element doesn't appear within `timeout_ms`

## Tips

1. **Be specific** - Use unique selectors to avoid clicking wrong elements
2. **Prefer IDs/data attributes** - More stable than classes which may change
3. **Add waits if needed** - If element appears after async load, increase timeout or add `sleep` before
4. **Check for overlays** - Modal dialogs or loading spinners may intercept clicks
