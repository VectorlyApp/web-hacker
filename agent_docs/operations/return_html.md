# return_html Operation

> Return raw HTML content from the full page or a specific element. Use when you need HTML for external parsing, or when data isn't available via API. Can target specific containers with CSS selectors.

Return HTML content from the page or a specific element.

## Basic Format

```json
{
  "type": "return_html",
  "scope": "page",
  "selector": null,
  "timeout_ms": 20000
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"return_html"` |
| `scope` | string | No | `"page"` | `"page"` for full page, `"element"` for specific element |
| `selector` | string | No | `null` | CSS selector (required if scope is `"element"`) |
| `timeout_ms` | int | No | `20000` | Max wait time for element |

## Examples

### Get Full Page HTML
```json
{
  "type": "return_html",
  "scope": "page"
}
```

### Get Element HTML
```json
{
  "type": "return_html",
  "scope": "element",
  "selector": "div.results"
}
```

### Get Table HTML
```json
{
  "type": "return_html",
  "scope": "element",
  "selector": "table#data-table"
}
```

### With Dynamic Selector
```json
{
  "type": "return_html",
  "scope": "element",
  "selector": "#content-{{section_id}}"
}
```

## Return Value

Sets `routine_execution_result.data` to the HTML string:

**Page scope:**
```html
<!DOCTYPE html><html><head>...</head><body>...</body></html>
```

**Element scope:**
```html
<div class="results"><p>Item 1</p><p>Item 2</p></div>
```

## When to Use

| Use Case | Operation |
|----------|-----------|
| Need raw HTML for parsing | `return_html` |
| Need structured JSON data | `fetch` or `js_evaluate` |
| Need specific data points | `js_evaluate` |
| Need file download | `download` |

## Typical Usage

### Scrape and Parse Later
```json
[
  {
    "type": "navigate",
    "url": "https://example.com/listings"
  },
  {
    "type": "return_html",
    "scope": "element",
    "selector": "ul.listing-items"
  }
]
```

### Get Full Page for Analysis
```json
[
  {
    "type": "navigate",
    "url": "https://example.com/page"
  },
  {
    "type": "sleep",
    "timeout_seconds": 2
  },
  {
    "type": "return_html",
    "scope": "page"
  }
]
```

## Notes

- **Page scope**: Returns `document.documentElement.outerHTML`
- **Element scope**: Returns `element.outerHTML`
- If selector not found, returns `null`
- HTML is returned as raw string (not parsed)
- Usually the final operation in a routine
