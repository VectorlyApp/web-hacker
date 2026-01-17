# Routines

> Routine structure, fields, placeholder syntax, and available operations list. Start here for routine format.

A **Routine** is the core automation unit - a JSON-serializable workflow that executes a sequence of operations.

## Routine Structure

```json
{
  "name": "amtrak_train_search",
  "description": "Search for train schedules on Amtrak",
  "incognito": true,
  "parameters": [...],
  "operations": [...]
}
```

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Routine identifier |
| `description` | string | Yes | Human-readable description |
| `operations` | list[Operation] | Yes | Sequential operations to execute (see `docs_operations.md`) |
| `parameters` | list[Parameter] | Yes | User-defined input parameters (see `docs_parameters.md`) |
| `incognito` | bool | No | Use incognito mode (default: true) |

## Placeholders

Placeholders use `{{name}}` syntax and are resolved at execution time. **See `docs_placeholders.md` for complete details.**

### User Parameters
Parameters defined in the routine's `parameters` array:
```json
"query": "\"{{search_term}}\""
"page": "{{page_number}}"
```

### Builtin Parameters
Available without definition:

| Placeholder | Description |
|-------------|-------------|
| `{{uuid}}` | Generates a random UUID (crypto.randomUUID()) |
| `{{epoch_milliseconds}}` | Current timestamp in ms (Date.now()) |

### Storage Placeholders
Resolved at runtime from browser context (**only in fetch `headers` and `body`**):

| Prefix | Description | Example (in JSON) |
|--------|-------------|-------------------|
| `sessionStorage:` | Browser sessionStorage | `"\"{{sessionStorage:auth.token}}\""` |
| `localStorage:` | Browser localStorage | `"\"{{localStorage:user.id}}\""` |
| `cookie:` | Cookie value | `"\"{{cookie:session_id}}\""` |
| `meta:` | Meta tag content | `"\"{{meta:csrf-token}}\""` |
| `window:` | Window property | `"\"{{window:__CONFIG__.apiKey}}\""` |

**Limitation:** Storage placeholders are NOT interpolated in URLs yet - only in fetch headers and body.

### Escape-Quoted Format (PLACEHOLDERS ONLY!)

**String placeholders MUST use escape-quoted format:**
```json
"name": "\"{{username}}\""
"body": {"query": "\"{{search_term}}\""}
```

**Why?** When the placeholder resolves, the outer quotes become part of the JSON string value. Without escape-quotes, `{{name}}` resolving to `John` produces invalid JSON.

**Non-string types** (int, number, bool) can use either format:
```json
"count": "{{limit}}"
"count": "\"{{limit}}\""
```

### HARDCODED VALUES: COPY FROM NETWORK TRAFFIC AS-IS

**The `\"` syntax is ONLY for placeholder resolution!** Hardcoded values should be copied exactly as observed in network traffic:

WRONG (adding escaped quotes to hardcoded):
```json
"type": "\"OW\""
"pricingUnit": "\"DOLLARS\""
```

RIGHT (copy from network traffic as-is):
```json
"type": "OW"
"pricingUnit": "DOLLARS"
```

**Mixed example:**
```json
{
  "code": "\"{{origin}}\"",
  "type": "OW",
  "active": true
}
```

---

## Validation Rules

### Parameter Usage
- All defined parameters MUST be used in operations
- No undefined parameters can appear in placeholders
- Builtin parameters (`uuid`, `epoch_milliseconds`) don't need definition

### Placeholder Quote Rules
String parameters MUST use escape-quoted format:
```json
"name": "\"{{username}}\""
```

Non-string types (int, number, bool) can use either:
```json
"count": "{{limit}}"
"count": "\"{{limit}}\""
```

## Available Operations

Operations are executed sequentially. **See `docs_operations.md` for detailed execution info, validations, and limitations.**

### Navigation & Timing
| Type | Description |
|------|-------------|
| `navigate` | Navigate to URL |
| `sleep` | Pause execution |
| `wait_for_url` | Wait for URL to match regex |

### Data Operations
| Type | Description |
|------|-------------|
| `fetch` | Execute HTTP request via browser fetch API (see `docs_endpoints.md`) |
| `return` | Retrieve result from sessionStorage |
| `download` | Download binary file as base64 |
| `get_cookies` | Get all cookies (including HttpOnly) via CDP |

### UI Automation
| Type | Description |
|------|-------------|
| `click` | Click element by CSS selector |
| `input_text` | Type text into input element |
| `press` | Press keyboard key |
| `scroll` | Scroll page or element |

### Data Retrieval
| Type | Description |
|------|-------------|
| `return_html` | Get HTML content from page/element |
| `js_evaluate` | Execute custom JavaScript (IIFE format) |

### Not Yet Implemented
- `hover` - Mouse hover
- `wait_for_selector` - Wait for element state
- `wait_for_title` - Wait for title match
- `set_files` - Set files for file input
- `return_screenshot` - Capture screenshot

---

## Execution Flow

**See `docs_execution.md` for complete execution context and result details.**

1. Creates or attaches to browser tab
2. Enables CDP domains (Page, Runtime, Network, DOM)
3. Iterates through operations sequentially
4. Each operation:
   - Interpolates parameters
   - Resolves placeholders
   - Executes via CDP
   - Collects metadata
5. Returns `RoutineExecutionResult`

## Example Routine

**See `docs_examples.md` for more complete real-world examples.**

```json
{
  "name": "arxiv_download",
  "description": "Download paper from arXiv",
  "incognito": true,
  "parameters": [
    {
      "name": "paper_id",
      "type": "string",
      "required": true,
      "description": "arXiv paper ID",
      "examples": ["1706.03762"]
    }
  ],
  "operations": [
    {
      "type": "download",
      "endpoint": {
        "url": "https://arxiv.org/pdf/\"{{paper_id}}\"",
        "method": "GET",
        "credentials": "omit"
      },
      "filename": "\"{{paper_id}}\".pdf"
    }
  ]
}
```
