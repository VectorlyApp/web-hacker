# fetch Operation

> Make HTTP API requests (GET, POST, PUT, DELETE) with headers, JSON bodies, and authentication. Supports dynamic placeholders for URLs, headers, and body. Store responses in sessionStorage for later use. Primary operation for retrieving structured JSON data from APIs.

Execute HTTP requests from the browser context. This is the primary operation for making API calls and retrieving data.

## Basic Format

```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/data",
    "method": "GET",
    "headers": {},
    "body": null,
    "credentials": "include"
  },
  "session_storage_key": "api_result"
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"fetch"` |
| `endpoint` | object | Yes | - | Request configuration (see below) |
| `session_storage_key` | string | No | null | Store response in session storage |

### Endpoint Object

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | Yes | - | Full URL to fetch |
| `method` | string | No | `"GET"` | HTTP method: GET, POST, PUT, DELETE, PATCH |
| `headers` | object | No | `{}` | Request headers as key-value pairs |
| `body` | any | No | `null` | Request body (for POST/PUT/PATCH) |
| `credentials` | string | No | `"include"` | Cookie handling: `"include"`, `"same-origin"`, `"omit"` |

## Using Placeholders

Placeholders are interpolated in URL, headers, and body.

### User Parameters
```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/users/{{user_id}}",
    "method": "GET"
  }
}
```

### String Parameters in Body (CRITICAL!)

**String parameters in JSON body MUST use escaped quotes:**

```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/search",
    "method": "POST",
    "body": {
      "query": "\"{{search_term}}\"",
      "limit": 10
    }
  }
}
```

Why? The placeholder `{{search_term}}` is replaced with raw text. Without escaped quotes:
- Input: `search_term = "hello"`
- Result: `{"query": hello, "limit": 10}` ← Invalid JSON!

With escaped quotes `\"{{search_term}}\"`:
- Input: `search_term = "hello"`
- Result: `{"query": "hello", "limit": 10}` ← Valid!

**Numbers and booleans don't need escaping:**
```json
{
  "body": {
    "count": "{{count}}",
    "active": "{{is_active}}"
  }
}
```

### Storage Placeholders in Headers/Body

Access previously stored data using prefix placeholders:

| Prefix | Source | Example |
|--------|--------|---------|
| `sessionStorage:` | Browser sessionStorage | `{{sessionStorage:auth_token}}` |
| `localStorage:` | Browser localStorage | `{{localStorage:user_id}}` |
| `cookie:` | Cookies | `{{cookie:session_id}}` |
| `meta:` | Page meta tags | `{{meta:csrf-token}}` |

```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/data",
    "method": "GET",
    "headers": {
      "Authorization": "Bearer {{sessionStorage:access_token}}",
      "X-CSRF-Token": "{{meta:csrf-token}}"
    }
  }
}
```

## Storing Results

Use `session_storage_key` to save the response for later use:

```json
[
  {
    "type": "fetch",
    "endpoint": {
      "url": "https://api.example.com/users",
      "method": "GET"
    },
    "session_storage_key": "users_data"
  },
  {
    "type": "return",
    "session_storage_key": "users_data"
  }
]
```

## Examples

### Simple GET Request
```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/products",
    "method": "GET"
  },
  "session_storage_key": "products"
}
```

### POST with JSON Body
```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/search",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "query": "\"{{search_query}}\"",
      "filters": {
        "category": "\"{{category}}\"",
        "min_price": "{{min_price}}"
      }
    }
  },
  "session_storage_key": "search_results"
}
```

### Authenticated Request
```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/profile",
    "method": "GET",
    "headers": {
      "Authorization": "Bearer {{sessionStorage:token}}",
      "X-Request-ID": "{{uuid}}"
    },
    "credentials": "include"
  },
  "session_storage_key": "profile"
}
```

### Form-Encoded POST
```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://example.com/login",
    "method": "POST",
    "headers": {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    "body": "username={{username}}&password={{password}}"
  },
  "session_storage_key": "login_response"
}
```

### GraphQL Query
```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/graphql",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "query": "query GetUser($id: ID!) { user(id: $id) { name email } }",
      "variables": {
        "id": "\"{{user_id}}\""
      }
    }
  },
  "session_storage_key": "graphql_result"
}
```

## Automatic Origin Navigation

If the browser is on `about:blank`, the fetch operation automatically navigates to the target domain first. This prevents CORS issues.

## Error Handling

The operation captures:
- HTTP errors (non-2xx responses)
- Network errors
- CORS errors
- Timeout errors

Failed fetches will raise a `RuntimeError` with details.

## Credentials Modes

| Mode | Behavior |
|------|----------|
| `"include"` | Send cookies with cross-origin requests (default) |
| `"same-origin"` | Only send cookies for same-origin requests |
| `"omit"` | Never send cookies |

## When to Use fetch vs Other Operations

| Use Case | Operation |
|----------|-----------|
| API call returning JSON | `fetch` |
| Download binary file (PDF, image) | `download` |
| Get page HTML content | `return_html` |
| Execute browser-side logic | `js_evaluate` |

## Common Mistakes

1. **Missing escaped quotes for string params in body** - Use `\"{{param}}\"`
2. **Forgetting Content-Type header** - Add `"Content-Type": "application/json"` for JSON bodies
3. **Wrong credentials mode** - Use `"include"` to send cookies
4. **Not storing result** - Add `session_storage_key` if you need the data later
5. **Using storage placeholders in URL** - Currently only supported in headers and body
