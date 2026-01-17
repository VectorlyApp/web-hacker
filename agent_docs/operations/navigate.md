# navigate Operation

> Navigate browser to a URL. Usually the first operation in a routine. Configurable wait time for page load (default 3s) to allow JS execution and storage population. Supports dynamic URLs with placeholders.

Navigate the browser to a URL.

## Basic Format

```json
{
  "type": "navigate",
  "url": "https://example.com",
  "sleep_after_navigation_seconds": 3.0
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"navigate"` |
| `url` | string | Yes | - | URL to navigate to |
| `sleep_after_navigation_seconds` | float | No | `3.0` | Wait time after navigation for page to load |

## Using Placeholders

URLs support parameter placeholders:
```json
{
  "type": "navigate",
  "url": "https://example.com/users/{{user_id}}/profile"
}
```

## Examples

### Simple Navigation
```json
{
  "type": "navigate",
  "url": "https://example.com"
}
```

### With Dynamic Path
```json
{
  "type": "navigate",
  "url": "https://example.com/search?q={{search_term}}"
}
```

### Longer Wait for Heavy Pages
```json
{
  "type": "navigate",
  "url": "https://slow-loading-site.com",
  "sleep_after_navigation_seconds": 5.0
}
```

### No Wait (Quick Navigation)
```json
{
  "type": "navigate",
  "url": "https://example.com/api-page",
  "sleep_after_navigation_seconds": 0
}
```

## Why Wait After Navigation?

The default 3-second wait allows:
- JavaScript to execute
- API calls to complete
- sessionStorage/localStorage to populate
- Dynamic content to render

This is important when subsequent operations need data that's loaded asynchronously.

## Typical Usage

Navigate is usually the **first operation** in a routine:

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
  }
]
```

## When to Skip Navigate

You can skip the initial navigate if:
- Using `fetch` operation only (auto-navigates to origin)
- Already on the correct page from a previous routine

## Notes

- Updates `current_url` in execution context
- Waits for page load event before sleep timer starts
- Placeholders in URL are interpolated before navigation
