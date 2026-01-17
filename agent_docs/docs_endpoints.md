# Endpoints

> HTTP endpoint config for fetch/download: URL, method, headers, body, credentials. MIME types reference.

Endpoints define HTTP request configurations for `fetch` and `download` operations.

## Endpoint Structure

```json
{
  "url": "https://api.example.com/search",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer {{sessionStorage:auth.token}}"
  },
  "body": {
    "query": "\"{{search_term}}\"",
    "limit": "{{limit}}"
  },
  "credentials": "same-origin",
  "description": "Search API endpoint"
}
```

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | Yes | - | Target URL with placeholders |
| `method` | HTTPMethod | No | GET | HTTP method |
| `headers` | dict | No | null | Request headers |
| `body` | dict | No | null | Request body (for POST/PUT/PATCH) |
| `credentials` | Credentials | No | same-origin | Cookie/auth handling |
| `description` | string | No | null | Human-readable description |

## HTTP Methods

```
GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD, CONNECT, TRACE
```

## Credentials Modes

| Mode | Description |
|------|-------------|
| `same-origin` | Send cookies for same-origin requests only |
| `include` | Always send cookies, even cross-origin |
| `omit` | Never send cookies |

## URL Placeholders

```json
{
  "url": "https://api.example.com/users/\"{{user_id}}\"/posts?limit=\"{{limit}}\""
}
```

## Headers with Placeholders

```json
{
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer {{sessionStorage:auth.access_token}}",
    "X-Request-ID": "{{uuid}}",
    "X-Timestamp": "{{epoch_milliseconds}}",
    "X-Session": "{{cookie:session_id}}"
  }
}
```

## Body Formats

### CRITICAL: Placeholders vs Hardcoded Values

**Escaped quotes `\"` are ONLY for placeholder resolution!**

Hardcoded values should be copied exactly as observed in network traffic.

| Value Type | JSON Syntax | Example |
|------------|-------------|---------|
| String placeholder | `"\"{{x}}\""` | `"name": "\"{{username}}\""` |
| Number placeholder | `"{{x}}"` | `"count": "{{count}}"` |
| Hardcoded string | `"value"` | `"type": "OW"` |
| Hardcoded number | `123` | `"limit": 100` |
| Hardcoded boolean | `true`/`false` | `"active": true` |

WRONG (adding escaped quotes to hardcoded values):
```json
"pricingUnit": "\"DOLLARS\""
"type": "\"OW\""
```

RIGHT (copy from network traffic as-is):
```json
"pricingUnit": "DOLLARS"
"type": "OW"
```

### JSON Body
```json
{
  "body": {
    "username": "\"{{username}}\"",
    "count": "{{count}}",
    "active": "{{is_active}}",
    "type": "search",
    "limit": 100,
    "data": {
      "nested": "\"{{nested_value}}\""
    }
  }
}
```

### Form Data (as JSON)
```json
{
  "headers": {
    "Content-Type": "application/x-www-form-urlencoded"
  },
  "body": {
    "field1": "\"{{value1}}\"",
    "field2": "\"{{value2}}\""
  }
}
```

## MIME Types

Common supported types:

### Documents
- `application/json`
- `application/pdf`
- `application/xml`
- `application/zip`

### Office
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (DOCX)
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (XLSX)
- `application/vnd.openxmlformats-officedocument.presentationml.presentation` (PPTX)

### Images
- `image/png`
- `image/jpeg`
- `image/gif`
- `image/webp`
- `image/svg+xml`

### Text
- `text/plain`
- `text/html`
- `text/css`
- `text/csv`

## Complete Example

```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.amtrak.com/services/search",
    "method": "POST",
    "description": "Search for train schedules",
    "headers": {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "x-amtrak-trace-id": "{{sessionStorage:ibsession.sessionid}}"
    },
    "body": {
      "origin": {
        "code": "\"{{origin}}\""
      },
      "destination": {
        "code": "\"{{destination}}\""
      },
      "departureDate": "\"{{departure_date}}\"",
      "travelers": {
        "adults": 1
      }
    },
    "credentials": "include"
  },
  "session_storage_key": "train_search_results"
}
```
