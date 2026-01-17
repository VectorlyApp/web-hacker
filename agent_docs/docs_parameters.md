# Parameters

> Parameter types (string, integer, date, enum), validation options, naming rules. Builtin parameters: uuid, epoch_milliseconds.

Parameters define user inputs for routines. They enable dynamic values to be injected at execution time.

---

## CRITICAL: JSON SERIALIZATION RULES FOR PARAMETERS

**ALL placeholder values MUST be valid JSON.** The format depends on the parameter type:

### String Parameters → ALWAYS use escaped quotes `\"`
```json
{
  "name": "\"{{username}}\"",
  "query": "\"{{search_query}}\""
}
```
Resolves to:
```json
{
  "name": "john",
  "query": "flights to NYC"
}
```

### Standalone Primitives (integer, number, boolean) → Outer quotes only
```json
{
  "limit": "{{limit}}",
  "price": "{{price}}",
  "active": "{{is_active}}"
}
```
Resolves to:
```json
{
  "limit": 50,
  "price": 19.99,
  "active": true
}
```

### Primitives WITHIN a String → Use escaped quotes `\"`
```json
{
  "url": "/api/users/\"{{user_id}}\"/posts",
  "message": "Page \"{{page}}\" of results"
}
```
Resolves to:
```json
{
  "url": "/api/users/123/posts",
  "message": "Page 5 of results"
}
```

---

## Quick Reference: Parameter Type → JSON Format

| Parameter Type | Standalone Value | Inside a String |
|----------------|------------------|-----------------|
| `string` | `"\"{{x}}\""` | `"prefix\"{{x}}\"suffix"` |
| `integer` | `"{{x}}"` | `"prefix\"{{x}}\"suffix"` |
| `number` | `"{{x}}"` | `"prefix\"{{x}}\"suffix"` |
| `boolean` | `"{{x}}"` | `"prefix\"{{x}}\"suffix"` |
| `date` | `"\"{{x}}\""` | `"prefix\"{{x}}\"suffix"` |
| `datetime` | `"\"{{x}}\""` | `"prefix\"{{x}}\"suffix"` |
| `email` | `"\"{{x}}\""` | `"prefix\"{{x}}\"suffix"` |
| `url` | `"\"{{x}}\""` | `"prefix\"{{x}}\"suffix"` |
| `enum` | `"\"{{x}}\""` | `"prefix\"{{x}}\"suffix"` |

**Key insight:** String-like types ALWAYS need `\"`. Primitives only need `\"` when embedded in a larger string.

---

## Parameter Structure

```json
{
  "name": "search_query",
  "type": "string",
  "required": true,
  "description": "The search term to look up",
  "default": null,
  "examples": ["flights to NYC", "hotel in Boston"],
  "min_length": 1,
  "max_length": 200,
  "pattern": null,
  "enum_values": null,
  "format": null
}
```

## Parameter Types

| Type | Description | Validation Options | JSON Format |
|------|-------------|-------------------|-------------|
| `string` | Text value | `min_length`, `max_length`, `pattern` | `"\"{{x}}\""` |
| `integer` | Whole number | `min_value`, `max_value` | `"{{x}}"` |
| `number` | Decimal number | `min_value`, `max_value` | `"{{x}}"` |
| `boolean` | true/false | - | `"{{x}}"` |
| `date` | Date string | `format` (e.g., "YYYY-MM-DD") | `"\"{{x}}\""` |
| `datetime` | Date+time string | `format` | `"\"{{x}}\""` |
| `email` | Email address | Pattern validated | `"\"{{x}}\""` |
| `url` | URL string | Pattern validated | `"\"{{x}}\""` |
| `enum` | One of allowed values | `enum_values` required | `"\"{{x}}\""` |

## All Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Parameter identifier (valid Python identifier) |
| `type` | ParameterType | No | Data type (default: "string") |
| `required` | bool | No | Is parameter required? (default: true) |
| `description` | string | Yes | Human-readable description |
| `default` | any | No | Default value if not provided |
| `examples` | list | No | Example values for documentation |
| `min_length` | int | No | Minimum string length |
| `max_length` | int | No | Maximum string length |
| `min_value` | number | No | Minimum numeric value |
| `max_value` | number | No | Maximum numeric value |
| `pattern` | string | No | Regex pattern for validation |
| `enum_values` | list[string] | No | Allowed values for enum type |
| `format` | string | No | Format specification |

## Naming Rules

Parameter names must:
- Be valid Python identifiers
- NOT start with reserved prefixes:
  - `sessionStorage`
  - `localStorage`
  - `cookie`
  - `meta`
  - `windowProperty`
  - `uuid`
  - `epoch_milliseconds`

## Builtin Parameters

These are automatically available without definition:

| Name | Type | Description |
|------|------|-------------|
| `uuid` | string | Generates unique UUID |
| `epoch_milliseconds` | string | Current time in epoch ms |

Usage:
```json
{
  "request_id": "\"{{uuid}}\"",
  "timestamp": "\"{{epoch_milliseconds}}\""
}
```

---

## Usage in Operations

### String Parameters (ALWAYS escape-quoted)

```json
{
  "body": {
    "name": "\"{{username}}\"",
    "email": "\"{{user_email}}\"",
    "query": "\"{{search_query}}\""
  }
}
```

### Integer/Number Parameters (standalone = outer quotes only)

```json
{
  "body": {
    "limit": "{{limit}}",
    "offset": "{{offset}}",
    "price": "{{price}}"
  }
}
```

### Boolean Parameters (standalone = outer quotes only)

```json
{
  "body": {
    "active": "{{is_active}}",
    "verified": "{{is_verified}}"
  }
}
```

### Mixed Example

```json
{
  "body": {
    "username": "\"{{username}}\"",
    "age": "{{age}}",
    "active": "{{is_active}}",
    "url": "https://api.example.com/users/\"{{user_id}}\"/posts?page=\"{{page}}\""
  }
}
```

Resolves to:
```json
{
  "body": {
    "username": "john",
    "age": 25,
    "active": true,
    "url": "https://api.example.com/users/123/posts?page=1"
  }
}
```

---

## Parameter Definition Examples

### String with Validation
```json
{
  "name": "email",
  "type": "email",
  "required": true,
  "description": "User email address",
  "pattern": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"
}
```
Usage: `"email": "\"{{email}}\""`

### Integer with Range
```json
{
  "name": "limit",
  "type": "integer",
  "required": false,
  "default": 20,
  "min_value": 1,
  "max_value": 100,
  "description": "Number of results to return"
}
```
Usage: `"limit": "{{limit}}"`

### Enum
```json
{
  "name": "sort_order",
  "type": "enum",
  "required": false,
  "default": "desc",
  "enum_values": ["asc", "desc"],
  "description": "Sort order for results"
}
```
Usage: `"sort": "\"{{sort_order}}\""`

### Date with Format
```json
{
  "name": "departure_date",
  "type": "date",
  "required": true,
  "format": "YYYY-MM-DD",
  "description": "Travel departure date",
  "examples": ["2026-08-22"]
}
```
Usage: `"date": "\"{{departure_date}}\""`

### Boolean
```json
{
  "name": "include_metadata",
  "type": "boolean",
  "required": false,
  "default": false,
  "description": "Whether to include metadata in response"
}
```
Usage: `"include_metadata": "{{include_metadata}}"`