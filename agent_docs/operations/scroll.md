# scroll Operation

> Scroll the page or scrollable containers. Use for infinite scroll pages, revealing lazy-loaded content, or scrolling to elements. Supports absolute position, relative delta, and smooth scrolling.

Scroll the page or a specific element.

## Basic Format

```json
{
  "type": "scroll",
  "selector": null,
  "x": null,
  "y": null,
  "delta_x": null,
  "delta_y": 500,
  "behavior": "auto",
  "timeout_ms": 20000
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"scroll"` |
| `selector` | string | No | `null` | CSS selector for element to scroll (null = window) |
| `x` | int | No | `null` | Absolute x position (window only) |
| `y` | int | No | `null` | Absolute y position (window only) |
| `delta_x` | int | No | `null` | Relative horizontal scroll amount |
| `delta_y` | int | No | `null` | Relative vertical scroll amount |
| `behavior` | string | No | `"auto"` | `"auto"` (instant) or `"smooth"` (animated) |
| `timeout_ms` | int | No | `20000` | Max wait time for element |

## Window vs Element Scrolling

**Window scroll** (no selector):
- Scrolls the entire page
- Supports both absolute (x, y) and relative (delta_x, delta_y)

**Element scroll** (with selector):
- Scrolls a scrollable container (overflow: scroll/auto)
- Only supports relative scrolling (delta_x, delta_y)

## Examples

### Scroll Down 500px
```json
{
  "type": "scroll",
  "delta_y": 500
}
```

### Scroll to Bottom of Page
```json
{
  "type": "scroll",
  "y": 99999
}
```

### Scroll to Top
```json
{
  "type": "scroll",
  "y": 0
}
```

### Smooth Scroll Down
```json
{
  "type": "scroll",
  "delta_y": 300,
  "behavior": "smooth"
}
```

### Scroll Inside Container
```json
{
  "type": "scroll",
  "selector": "div.scrollable-list",
  "delta_y": 200
}
```

### Horizontal Scroll
```json
{
  "type": "scroll",
  "delta_x": 300
}
```

### Scroll to Specific Position
```json
{
  "type": "scroll",
  "x": 0,
  "y": 1000
}
```

## Typical Usage

### Load Infinite Scroll Content
```json
[
  {
    "type": "navigate",
    "url": "https://example.com/feed"
  },
  {
    "type": "scroll",
    "delta_y": 1000
  },
  {
    "type": "sleep",
    "timeout_seconds": 1
  },
  {
    "type": "scroll",
    "delta_y": 1000
  },
  {
    "type": "sleep",
    "timeout_seconds": 1
  },
  {
    "type": "js_evaluate",
    "js": "(function() { return document.querySelectorAll('.feed-item').length; })()"
  }
]
```

### Scroll to Reveal Element
```json
[
  {
    "type": "scroll",
    "delta_y": 800
  },
  {
    "type": "click",
    "selector": "button.load-more"
  }
]
```

## Scroll Behavior

| Value | Effect |
|-------|--------|
| `"auto"` | Instant scroll (default) |
| `"smooth"` | Animated scroll |

Use `"smooth"` when the site might detect instant scrolling as bot behavior.

## Notes

- Positive `delta_y` = scroll down
- Negative `delta_y` = scroll up
- Positive `delta_x` = scroll right
- Negative `delta_x` = scroll left
- Use absolute `y` for specific positions
- Small sleep after scroll lets lazy content load
