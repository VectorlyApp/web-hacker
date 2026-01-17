# Operations

> Each operation type with CDP execution details, validations, and limitations. Reference when building operations.

Operations are the building blocks of routines. Each operation type performs a specific browser action via Chrome DevTools Protocol (CDP).

## Operation Execution Model

All operations:
1. Extend `RoutineOperation` base class
2. Implement `_execute_operation(context: RoutineExecutionContext)`
3. Automatic metadata collection (type, duration, errors, details)
4. Parameters interpolated via `apply_params()` before execution

```python
# Base execution flow (simplified)
def execute(self, context):
    context.current_operation_metadata = OperationExecutionMetadata(type=self.type)
    start = time.perf_counter()
    try:
        self._execute_operation(context)
    except Exception as e:
        context.current_operation_metadata.error = str(e)
    finally:
        context.current_operation_metadata.duration_seconds = time.perf_counter() - start
        context.result.operations_metadata.append(context.current_operation_metadata)
```

---

## Navigation & Timing

### `navigate`
Navigate to a URL.

```json
{
  "type": "navigate",
  "url": "https://example.com/search?q=\"{{query}}\"",
  "sleep_after_navigation_seconds": 3.0
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | Target URL with placeholders |
| `sleep_after_navigation_seconds` | float | 3.0 | Wait time after navigation |

**Execution:**
1. Interpolates placeholders in URL via `apply_params()`
2. Sends CDP `Page.navigate` command with the URL
3. Updates `context.current_url` to track navigation state
4. Sleeps for `sleep_after_navigation_seconds` to allow JS to execute and populate storage

**Why the sleep?** Pages often load JavaScript that populates localStorage/sessionStorage asynchronously. The sleep ensures these values are available for subsequent operations.

---

### `sleep`
Pause execution.

```json
{
  "type": "sleep",
  "timeout_seconds": 2.0
}
```

**Execution:** Simple `time.sleep(timeout_seconds)` - blocks the routine for the specified duration.

---

## Data Operations

### `fetch`
Execute HTTP request via JavaScript fetch API in the browser context.

```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/search",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer {{sessionStorage:auth.token}}"
    },
    "body": {
      "query": "\"{{search_term}}\""
    },
    "credentials": "same-origin"
  },
  "session_storage_key": "search_results"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `endpoint` | Endpoint | Request configuration (see `docs_endpoints.md`) |
| `session_storage_key` | string? | Key to store response in sessionStorage |

**Execution:**
1. **CORS handling:** If current page is `about:blank`, automatically navigates to the target origin first to avoid CORS errors
2. Interpolates all placeholders in URL, headers, and body
3. Generates JavaScript using `generate_fetch_js()` that:
   - Resolves storage/meta placeholders at runtime
   - Executes `fetch()` with the configured options
   - Stores result in sessionStorage if `session_storage_key` provided
4. Sends CDP `Runtime.evaluate` with `awaitPromise: true`
5. Collects resolved placeholder values and stores in `result.placeholder_resolution`
6. Stores request/response metadata for debugging

**Limitations:**
- WebSocket not available in context
- Timeout controlled by `context.timeout` (default from routine)

---

### `return`
Retrieve result from browser sessionStorage and set as routine result.

```json
{
  "type": "return",
  "session_storage_key": "search_results"
}
```

**Execution:**
1. Gets total length of stored value via `generate_get_session_storage_length_js()`
2. Retrieves data in **256KB chunks** via `generate_get_session_storage_chunk_js()` to avoid CDP message size limits
3. Attempts to parse as JSON, falls back to `ast.literal_eval`, then raw string
4. Sets `context.result.data` with the parsed value

**Why chunking?** Large responses can exceed CDP's message size limits. Chunked retrieval ensures reliable transfer of any size response.

---

### `download`
Download binary files (PDF, images, etc.) and return as base64.

```json
{
  "type": "download",
  "endpoint": {
    "url": "https://example.com/file.pdf",
    "method": "GET"
  },
  "filename": "document.pdf"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `endpoint` | Endpoint | Request configuration |
| `filename` | string | **Required.** Output filename |

**Execution:**
1. Interpolates placeholders in endpoint and filename
2. Generates JavaScript via `generate_download_js()` that:
   - Fetches as `arrayBuffer`
   - Converts to base64 string
   - Stores in `window.__downloadData` for chunked retrieval
3. Retrieves base64 data in **256KB chunks** via `generate_get_download_chunk_js()`
4. Sets result:
   - `result.data` = base64 string
   - `result.is_base64` = true
   - `result.content_type` = response Content-Type
   - `result.filename` = configured filename

**Returns:**
```json
{
  "data": "<base64-encoded-content>",
  "content_type": "application/pdf",
  "filename": "document.pdf",
  "is_base64": true
}
```

---

## UI Automation

### `click`
Click element by CSS selector using CDP Input domain.

```json
{
  "type": "click",
  "selector": "#submit-button",
  "button": "left",
  "click_count": 1,
  "timeout_ms": 20000,
  "ensure_visible": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | required | CSS selector |
| `button` | "left"\|"right"\|"middle" | "left" | Mouse button |
| `click_count` | int | 1 | Number of clicks |
| `timeout_ms` | int | 20000 | Timeout in ms |
| `ensure_visible` | bool | true | Scroll into view first |

**Execution:**
1. Interpolates placeholders in selector
2. Executes `generate_click_js()` via `Runtime.evaluate` which:
   - Finds element by selector
   - **Validates element is visible** (not hidden honeypot)
   - Scrolls into view if `ensure_visible`
   - Returns center coordinates (x, y) and element profile
3. Stores element profile in operation metadata
4. Performs click(s) using CDP `Input.dispatchMouseEvent`:
   - `mousePressed` event
   - 50ms delay
   - `mouseReleased` event
   - 100ms delay between multiple clicks

**Safety:** Automatically validates element visibility to avoid clicking hidden honeypot traps.

---

### `input_text`
Type text into input element character by character.

```json
{
  "type": "input_text",
  "selector": "input[name='search']",
  "text": "\"{{query}}\"",
  "clear": true,
  "timeout_ms": 20000
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | required | CSS selector |
| `text` | string | required | Text with placeholders |
| `clear` | bool | false | Clear existing text first |
| `timeout_ms` | int | 20000 | Timeout in ms |

**Execution:**
1. Interpolates placeholders in selector and text
2. Executes `generate_type_js()` via `Runtime.evaluate` which:
   - Finds and focuses element
   - **Validates element is visible** (not hidden honeypot)
   - Clears existing text if `clear: true`
   - Returns element profile
3. Types text **character by character** using CDP `Input.dispatchKeyEvent`:
   - `keyDown` event
   - `keyUp` event
   - 20ms delay between characters

**Why character-by-character?** Simulates real user typing, triggers proper input events, and works with autocomplete/validation systems.

---

### `press`
Press a keyboard key.

```json
{
  "type": "press",
  "key": "enter"
}
```

**Supported keys:**
| Key Name | CDP Key |
|----------|---------|
| `enter` | Enter |
| `tab` | Tab |
| `escape`, `esc` | Escape |
| `backspace` | Backspace |
| `delete` | Delete |
| `arrowup/down/left/right` | Arrow* |
| `home`, `end` | Home, End |
| `pageup`, `pagedown` | Page* |
| `space` | " " |
| `shift`, `control/ctrl`, `alt`, `meta` | Modifier keys |

**Execution:**
1. Maps key name to CDP key code
2. Sends CDP `Input.dispatchKeyEvent`:
   - `keyDown` event
   - ~52ms delay
   - `keyUp` event

---

### `scroll`
Scroll page or element.

```json
{
  "type": "scroll",
  "selector": null,
  "delta_y": 500,
  "behavior": "smooth"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `selector` | string? | CSS selector (null = window) |
| `x`, `y` | int? | Absolute position (window only) |
| `delta_x`, `delta_y` | int? | Relative scroll |
| `behavior` | "auto"\|"smooth" | Scroll behavior |

**Execution:**
- **Element scroll:** Uses `generate_scroll_element_js()` - finds element and calls `scrollBy()`
- **Window scroll:** Uses `generate_scroll_window_js()` - calls `window.scrollTo()` or `window.scrollBy()`

---

## Waiting & Observation

### `wait_for_url`
Wait for URL to match regex pattern.

```json
{
  "type": "wait_for_url",
  "url_regex": ".*results.*",
  "timeout_ms": 20000
}
```

**Execution:**
1. Generates JavaScript via `generate_wait_for_url_js()` that checks `window.location.href` against regex
2. **Polls every 200ms** until match or timeout
3. Raises `RuntimeError` with current URL if timeout exceeded

---

### `wait_for_title`
Wait for page title to match regex. *(Not yet implemented)*

```json
{
  "type": "wait_for_title",
  "title_regex": "Search Results.*",
  "timeout_ms": 20000
}
```

---

### `wait_for_selector`
Wait for element state. *(Not yet implemented)*

```json
{
  "type": "wait_for_selector",
  "selector": ".results-loaded",
  "state": "visible",
  "timeout_ms": 20000
}
```

| State | Description |
|-------|-------------|
| `visible` | Element exists and is visible |
| `hidden` | Element exists but is hidden |
| `attached` | Element exists in DOM |
| `detached` | Element removed from DOM |

---

### `get_cookies`
Retrieve all cookies (including HttpOnly) via CDP.

```json
{
  "type": "get_cookies",
  "session_storage_key": "cookies",
  "domain_filter": "example.com"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_storage_key` | string | required | Key to store cookies |
| `domain_filter` | string | "*" | Domain filter ("*" for all) |

**Validation:** `domain_filter` cannot be empty (stripped and validated).

**Execution:**
1. Sends CDP `Network.getAllCookies` command
2. Filters cookies by domain if `domain_filter != "*"`
3. Stores JSON array in sessionStorage via `generate_store_in_session_storage_js()`

**Why CDP?** JavaScript `document.cookie` cannot access HttpOnly cookies. CDP provides access to all cookies including secure ones.

---

## Data Retrieval

### `return_html`
Get HTML content from page or element.

```json
{
  "type": "return_html",
  "scope": "element",
  "selector": "#results",
  "timeout_ms": 20000
}
```

| Scope | Description |
|-------|-------------|
| `page` | Full page `document.documentElement.outerHTML` |
| `element` | Selected element's `outerHTML` |

**Execution:**
1. Generates JavaScript via `generate_get_html_js(selector?)`
2. Evaluates via CDP `Runtime.evaluate`
3. Sets `context.result.data` to HTML string

---

### `return_screenshot`
Capture screenshot as base64. *(Not yet implemented)*

```json
{
  "type": "return_screenshot",
  "full_page": false,
  "timeout_ms": 20000
}
```

---

## Code Execution

### `js_evaluate`
Execute custom JavaScript in IIFE format with strict validation.

```json
{
  "type": "js_evaluate",
  "js": "(function() { return document.title; })()",
  "timeout_seconds": 5.0,
  "session_storage_key": "page_title"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `js` | string | required | JavaScript in IIFE format |
| `timeout_seconds` | float | 5.0 | Max execution time (max: 10s) |
| `session_storage_key` | string? | null | Optional storage key |

**Format Requirement:**
Code MUST be wrapped in an IIFE:
- `(function() { ... })()`
- `(() => { ... })()`
- `(async function() { ... })()`
- `(async () => { ... })()`

**Allowed:**
- Promises, async/await
- setTimeout/setInterval
- DOM manipulation
- Loops (timeout prevents infinite loops)
- Synchronous operations

**Blocked Patterns (regex validated):**
| Pattern | Reason |
|---------|--------|
| `eval(`, `Function(` | Dynamic code generation |
| `fetch(`, `XMLHttpRequest`, `WebSocket`, `sendBeacon` | Network requests (use fetch operation instead) |
| `addEventListener(`, `on*=` | Persistent event hooks |
| `MutationObserver`, `IntersectionObserver` | Persistent observers |
| `window.close(`, `location.`, `history.` | Navigation/lifecycle control |

**Additional Validations:**
1. **Syntax check:** Balanced brackets and terminated strings via `assert_balanced_js_delimiters()`
2. **IIFE format:** Regex validates proper wrapper format
3. **No storage placeholders:** `{{sessionStorage:...}}`, `{{localStorage:...}}`, etc. are blocked - access storage directly in JS
4. **No builtin placeholders:** `{{uuid}}`, `{{epoch_milliseconds}}` blocked - use `crypto.randomUUID()` or `Date.now()` instead
5. **Timeout limit:** Must be > 0 and <= 10 seconds
6. **Post-interpolation validation:** Code is re-validated after parameter substitution to prevent injection

**Execution:**
1. Interpolates user parameters into JS code
2. Re-validates code (prevents injection attacks)
3. Wraps in outer IIFE via `generate_js_evaluate_wrapper_js()` that:
   - Captures console.log output
   - Handles errors gracefully
   - Stores result if `session_storage_key` provided
4. Sends CDP `Runtime.evaluate` with `awaitPromise: true`
5. Stores console logs and errors in operation metadata

---

## Currently Unimplemented Operations

These operations are defined but not yet in the active union:
- `hover` - Mouse hover over element
- `wait_for_selector` - Wait for element state
- `wait_for_title` - Wait for title match
- `set_files` - Set files for file input
- `return_screenshot` - Capture screenshot
- `network_sniffing` - Background network interception

---

## Operation Metadata

Every operation execution collects metadata:

```python
class OperationExecutionMetadata:
    type: RoutineOperationTypes  # Operation type
    duration_seconds: float       # Execution time
    error: str | None            # Error message if failed
    details: dict                # Operation-specific data
```

**Common details by operation:**
- `click`: `selector`, `element`, `click_coordinates`
- `input_text`: `selector`, `text_length`, `element`
- `fetch/download`: `request`, `response`
- `js_evaluate`: `console_logs`, `execution_error`, `storage_error`
