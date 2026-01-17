# sleep Operation

> Pause execution for a specified duration (seconds). Use when timing is unpredictable - after clicks that trigger loading, between rapid actions, or waiting for animations. Prefer wait_for_url when possible.

Pause execution for a specified duration.

## Basic Format

```json
{
  "type": "sleep",
  "timeout_seconds": 2.0
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"sleep"` |
| `timeout_seconds` | float | Yes | - | Duration to sleep in seconds |

## Examples

### Wait 2 Seconds
```json
{
  "type": "sleep",
  "timeout_seconds": 2.0
}
```

### Short Wait for Animation
```json
{
  "type": "sleep",
  "timeout_seconds": 0.5
}
```

### Long Wait for Processing
```json
{
  "type": "sleep",
  "timeout_seconds": 10.0
}
```

## When to Use

| Scenario | Recommended Sleep |
|----------|-------------------|
| Wait for animation | 0.3-0.5s |
| Wait for API response | 1-2s |
| Wait for page load | 2-3s |
| Wait for heavy processing | 5-10s |

## Typical Usage

### After Click That Triggers Load
```json
[
  {
    "type": "click",
    "selector": "button.load-more"
  },
  {
    "type": "sleep",
    "timeout_seconds": 1.5
  },
  {
    "type": "js_evaluate",
    "js": "(function() { return document.querySelectorAll('.item').length; })()"
  }
]
```

### Between Rapid Actions
```json
[
  {
    "type": "input_text",
    "selector": "input#search",
    "text": "{{query}}"
  },
  {
    "type": "sleep",
    "timeout_seconds": 0.5
  },
  {
    "type": "click",
    "selector": ".autocomplete-suggestion:first-child"
  }
]
```

## sleep vs wait_for_url

| Approach | Use When |
|----------|----------|
| `sleep` | Unknown timing, simple delay |
| `wait_for_url` | Known URL change, more precise |

Prefer `wait_for_url` when possible - it's more reliable and often faster.

## Notes

- Supports fractional seconds (0.5, 1.5, etc.)
- Does not interact with the page
- Execution continues after timeout
- No upper limit, but keep reasonable for routine performance
