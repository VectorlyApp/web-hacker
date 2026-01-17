# js_evaluate Operation

> Extract hidden DOM elements (CSRF tokens, nonces), get reCAPTCHA tokens, scrape/format HTML tables, transform stored data (remember: fetch results are STRINGS - use JSON.parse()!), poll for dynamic content. Use console.log() for debugging - logs appear in operation metadata!

Execute JavaScript code directly in the browser context. Use this for DOM manipulation, data extraction, or custom logic that other operations cannot handle.

## Basic Format

```json
{
  "type": "js_evaluate",
  "js": "(function() { /* your code here */ })()",
  "timeout_seconds": 5,
  "session_storage_key": "optional_key_to_store_result"
}
```

## CRITICAL: IIFE Requirement

**ALL JavaScript code MUST be wrapped in an IIFE (Immediately Invoked Function Expression).**

Valid formats:
```javascript
// Standard function
(function() { return document.title; })()

// Arrow function
(() => { return document.title; })()

// Async function (for promises)
(async function() { return await somePromise; })()

// Async arrow
(async () => { return await somePromise; })()
```

**INVALID - Will be rejected:**
```javascript
// No IIFE wrapper
document.title

// Missing parentheses
function() { return document.title; }()

// Not immediately invoked
(function() { return document.title; })
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"js_evaluate"` |
| `js` | string | Yes | - | JavaScript code in IIFE format |
| `timeout_seconds` | float | No | 5.0 | Max execution time (1-10 seconds) |
| `session_storage_key` | string | No | null | Store result in session storage for later retrieval |

## What's ALLOWED

- **Promises and async/await**: `new Promise()`, `.then()`, `await`
- **Timers**: `setTimeout`, `setInterval` (useful for polling)
- **Loops**: `while`, `for`, `do` (timeout prevents infinite loops)
- **DOM manipulation**: Query, modify, create elements
- **Synchronous operations**: All standard JS

## What's BLOCKED (Security)

These patterns are detected and rejected:

| Pattern | Reason |
|---------|--------|
| `eval()` | Dynamic code generation |
| `Function()` constructor | Dynamic code generation |
| `fetch()` | Network requests (use `fetch` operation instead) |
| `XMLHttpRequest` | Network requests |
| `WebSocket` | Network requests |
| `sendBeacon` | Network/exfiltration |
| `addEventListener()` | Persistent event hooks |
| `on*=` handlers | Persistent event hooks |
| `MutationObserver` | Persistent observers |
| `IntersectionObserver` | Persistent observers |
| `window.close()` | Navigation/lifecycle |
| `location.*` | Navigation |
| `history.*` | Navigation |

## Placeholders in js_evaluate

**User-defined parameters ARE interpolated:**
```json
{
  "type": "js_evaluate",
  "js": "(function() { return document.querySelector('{{selector}}').textContent; })()"
}
```
If `selector` is a routine parameter, it will be replaced.

**Storage/meta placeholders are NOT interpolated in JS:**
```javascript
// WRONG - will error
(function() { return '{{sessionStorage:myKey}}'; })()

// RIGHT - access directly in JS
(function() { return sessionStorage.getItem('myKey'); })()
```

**Builtin parameters (epoch_milliseconds, uuid) are NOT interpolated:**
```javascript
// WRONG - will error
(function() { return '{{uuid}}'; })()

// RIGHT - use native JS
(function() { return crypto.randomUUID(); })()
(function() { return Date.now(); })()
```

## Storing Results

Use `session_storage_key` to store the result for later retrieval with a `return` operation:

```json
[
  {
    "type": "js_evaluate",
    "js": "(function() { return { title: document.title, url: window.location.href }; })()",
    "session_storage_key": "page_info"
  },
  {
    "type": "return",
    "session_storage_key": "page_info"
  }
]
```

## Examples

### Extract text from elements
```json
{
  "type": "js_evaluate",
  "js": "(function() { return Array.from(document.querySelectorAll('h2')).map(el => el.textContent); })()",
  "session_storage_key": "headings"
}
```

### Wait for element to appear (polling)
```json
{
  "type": "js_evaluate",
  "js": "(async function() { for (let i = 0; i < 50; i++) { const el = document.querySelector('.loaded'); if (el) return el.textContent; await new Promise(r => setTimeout(r, 100)); } throw new Error('Element not found'); })()",
  "timeout_seconds": 6
}
```

### Parse and transform data
```json
{
  "type": "js_evaluate",
  "js": "(function() { const raw = sessionStorage.getItem('api_response'); const data = JSON.parse(raw); return data.items.filter(i => i.active).map(i => ({ id: i.id, name: i.name })); })()",
  "session_storage_key": "filtered_items"
}
```

### Get computed styles
```json
{
  "type": "js_evaluate",
  "js": "(function() { const el = document.querySelector('{{selector}}'); const styles = window.getComputedStyle(el); return { color: styles.color, display: styles.display }; })()"
}
```

### Extract table data
```json
{
  "type": "js_evaluate",
  "js": "(function() { const rows = document.querySelectorAll('table tbody tr'); return Array.from(rows).map(row => { const cells = row.querySelectorAll('td'); return { name: cells[0]?.textContent?.trim(), value: cells[1]?.textContent?.trim() }; }); })()",
  "session_storage_key": "table_data"
}
```

## Debugging with console.log

**IMPORTANT: Use `console.log()` liberally for debugging!** All console output is captured in the operation metadata (`console_logs` field). This is extremely helpful for:

- Inspecting intermediate values during extraction
- Checking what elements were found
- Debugging why data isn't being extracted correctly
- Verifying selector matches

```javascript
(function() {
  const rows = document.querySelectorAll('table tr');
  console.log('Found rows:', rows.length);  // Shows up in metadata!

  const data = Array.from(rows).map(row => {
    const cells = row.querySelectorAll('td');
    console.log('Row cells:', cells.length, cells[0]?.textContent);
    return { name: cells[0]?.textContent };
  });

  console.log('Extracted data:', JSON.stringify(data));
  return data;
})()
```

## Error Handling

Errors and logs are captured in operation metadata:
- `console_logs`: All `console.log()` output - **very helpful for debugging!**
- `execution_error`: If your JS throws an exception
- `storage_error`: If storing to session storage fails

If an error occurs, the operation will raise a `RuntimeError` with the error message.

## When to Use js_evaluate vs Other Operations

| Use Case | Recommended Operation |
|----------|----------------------|
| Click a button | `click` |
| Type into input | `input_text` |
| Make HTTP request | `fetch` |
| Navigate to URL | `navigate` |
| Wait for URL change | `wait_for_url` |
| Get page HTML | `return_html` |
| **Custom DOM extraction** | `js_evaluate` |
| **Transform stored data** | `js_evaluate` |
| **Complex conditional logic** | `js_evaluate` |
| **Poll for dynamic content** | `js_evaluate` |

## Common Mistakes

1. **Forgetting IIFE wrapper** - Code must be `(function() { ... })()`
2. **Not parsing stored fetch data** - Data from `fetch` is stored as JSON STRING! You MUST parse it:
   ```javascript
   // WRONG - data is a string, not an object!
   const data = sessionStorage.getItem('api_result');
   return data.items;  // ERROR: undefined

   // RIGHT - parse the JSON string first!
   const data = JSON.parse(sessionStorage.getItem('api_result'));
   return data.items;  // Works!
   ```
3. **Using fetch()** - Blocked; use `fetch` operation instead
4. **Using storage placeholders** - Access `sessionStorage` directly in JS
5. **Timeout too short** - Increase for async operations
6. **Not returning a value** - Add explicit `return` statement
