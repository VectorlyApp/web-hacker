# return Operation

> Retrieve stored data from sessionStorage and return it as the routine's final result. Handles large data via chunking. Auto-parses JSON. Usually the last operation after fetch or js_evaluate has stored data.

Retrieve data from session storage and set it as the routine's final result.

## Basic Format

```json
{
  "type": "return",
  "session_storage_key": "my_data"
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"return"` |
| `session_storage_key` | string | Yes | - | Key to retrieve from session storage |

## How It Works

1. **Reads session storage** - Gets value stored under the specified key
2. **Handles large data** - Retrieves in 256KB chunks to avoid memory issues
3. **Parses JSON** - Attempts to parse as JSON; falls back to raw string
4. **Sets result** - Assigns parsed data to `routine_execution_result.data`

## Typical Pattern

Store data with `fetch` or `js_evaluate`, then retrieve with `return`:

```json
[
  {
    "type": "fetch",
    "endpoint": {
      "url": "https://api.example.com/data",
      "method": "GET"
    },
    "session_storage_key": "api_response"
  },
  {
    "type": "return",
    "session_storage_key": "api_response"
  }
]
```

## Examples

### Return Fetch Result
```json
[
  {
    "type": "fetch",
    "endpoint": {"url": "https://api.example.com/users"},
    "session_storage_key": "users"
  },
  {
    "type": "return",
    "session_storage_key": "users"
  }
]
```

### Return JS Evaluation Result
```json
[
  {
    "type": "js_evaluate",
    "js": "(function() { return Array.from(document.querySelectorAll('h1')).map(h => h.textContent); })()",
    "session_storage_key": "headings"
  },
  {
    "type": "return",
    "session_storage_key": "headings"
  }
]
```

### Multiple Data Sources
```json
[
  {
    "type": "fetch",
    "endpoint": {"url": "https://api.example.com/users"},
    "session_storage_key": "users"
  },
  {
    "type": "fetch",
    "endpoint": {"url": "https://api.example.com/products"},
    "session_storage_key": "products"
  },
  {
    "type": "js_evaluate",
    "js": "(function() { const users = JSON.parse(sessionStorage.getItem('users')); const products = JSON.parse(sessionStorage.getItem('products')); return { users: users, products: products, combined: true }; })()",
    "session_storage_key": "combined_data"
  },
  {
    "type": "return",
    "session_storage_key": "combined_data"
  }
]
```

## Data Flow

```
fetch/js_evaluate → sessionStorage → return → routine result
        ↓                  ↓              ↓
   stores data        holds data     extracts data
```

## Return vs Other Final Operations

| Operation | Output Type | Use Case |
|-----------|-------------|----------|
| `return` | JSON/text from sessionStorage | Structured data |
| `return_html` | HTML string | Page content |
| `download` | Base64 binary | Files (PDF, images) |

## Important Notes

1. **Usually the last operation** - Return sets the final result
2. **Key must exist** - Returns `null` if key doesn't exist
3. **JSON preferred** - Store JSON strings for structured data
4. **Large data OK** - Chunked retrieval handles large responses

## Error Handling

- If key doesn't exist: `result.data = null`
- If value is not JSON: Returns raw string
- If retrieval fails: Throws `RuntimeError`
