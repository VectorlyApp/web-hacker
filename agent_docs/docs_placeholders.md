# Placeholders

> Placeholder syntax and JSON quote rules for dynamic value injection at runtime (parameters of the routine or values from session storage, cookies, local storage, or built-ins). This must be learned before writing routines!

Placeholders are dynamic value references that get resolved at execution time.

---

## CRITICAL: SERIALIZATION RULES

**ALL placeholder values MUST be valid JSON.** This means every placeholder MUST be wrapped in quotes.

There are exactly **TWO** valid formats:

### 1. STANDALONE PRIMITIVES (number, boolean, null)

Use outer quotes only - they get stripped during resolution:

```json
"key": "{{param}}"
```

- Resolves `"{{limit}}"` → `50` (number)
- Resolves `"{{is_active}}"` → `true` (boolean)
- Resolves `"{{nothing}}"` → `null` (null)

### 2. STRING VALUES (ALWAYS use escaped quotes!)

String parameters and string sources MUST have escaped quotes `\"` around the placeholder:

```json
"key": "\"{{param}}\""
```

- Resolves `"\"{{username}}\""` → `"john"` (string)

### 3. PRIMITIVES WITHIN A LARGER STRING

When embedding ANY value inside a string, use escaped quotes:

```json
"message": "User \"{{user_id}}\" logged in"
```

- Resolves → `"User 123 logged in"`

---

## The Golden Rules

| Value Type                           | JSON Syntax                 | Example Resolution    |
| ------------------------------------ | --------------------------- | --------------------- |
| **String param**               | `"\"{{x}}\""`             | `"john"`            |
| **Number param** (standalone)  | `"{{x}}"`                 | `50`                |
| **Boolean param** (standalone) | `"{{x}}"`                 | `true`              |
| **Null param** (standalone)    | `"{{x}}"`                 | `null`              |
| **ANY value in string**        | `"prefix\"{{x}}\"suffix"` | `"prefix123suffix"` |

**NEVER write `{{param}}` without quotes! It's not valid JSON!**

WRONG: `"count": {{limit}}`
RIGHT: `"count": "{{limit}}"`

WRONG: `"name": {{username}}`
RIGHT: `"name": "\"{{username}}\""`

---

## HARDCODED VALUES: COPY FROM NETWORK TRAFFIC AS-IS

**The `\"` syntax is ONLY for placeholder resolution!**

Hardcoded strings should be written exactly as observed in the network traffic - which is normal JSON:

WRONG: `"type": "\"OW\""` (adding escaped quotes to hardcoded value)
RIGHT: `"type": "OW"` (just copy what the network traffic shows)

**The rule is simple:**

- **Placeholders** → need `\"` for string resolution
- **Hardcoded values** → copy directly from network traffic (normal JSON)

**Mixed example (placeholder + hardcoded):**

```json
{
  "code": "\"{{origin}}\"",
  "type": "OW",
  "pricingUnit": "DOLLARS",
  "limit": 100,
  "active": true
}
```

- `"\"{{origin}}\""` → placeholder, needs escaped quotes for resolution
- `"OW"`, `"DOLLARS"` → hardcoded strings, copied from network traffic
- `100`, `true` → hardcoded primitives, copied from network traffic

---

## Placeholder Syntax

- **Parameters**: `{{param_name}}` (NO prefix, name matches parameter definition)
- **Sources** (use dot paths):
  - `{{cookie:name}}`
  - `{{sessionStorage:path.to.value}}`
  - `{{localStorage:key}}`
  - `{{windowProperty:obj.key}}`
  - `{{meta:tag-name}}`

---

## Placeholder Types

### 1. User Parameters

Direct parameter references (no prefix):

| Parameter Type | JSON Syntax            | Resolves To |
| -------------- | ---------------------- | ----------- |
| String         | `"\"{{username}}\""` | `"john"`  |
| Integer        | `"{{limit}}"`        | `50`      |
| Number         | `"{{price}}"`        | `19.99`   |
| Boolean        | `"{{is_active}}"`    | `true`    |

### 2. Session Storage

Access sessionStorage values (including nested dot paths):

| Placeholder                                     | JSON Syntax                                           |
| ----------------------------------------------- | ----------------------------------------------------- |
| `{{sessionStorage:key}}`                      | `"\"{{sessionStorage:key}}\""`                      |
| `{{sessionStorage:auth.access_token}}`        | `"\"{{sessionStorage:auth.access_token}}\""`        |
| `{{sessionStorage:response.data.items.0.id}}` | `"\"{{sessionStorage:response.data.items.0.id}}\""` |

### 3. Local Storage

Access localStorage values:

| Placeholder                           | JSON Syntax                                 |
| ------------------------------------- | ------------------------------------------- |
| `{{localStorage:user_preferences}}` | `"\"{{localStorage:user_preferences}}\""` |
| `{{localStorage:settings.theme}}`   | `"\"{{localStorage:settings.theme}}\""`   |

### 4. Cookies

Access cookie values:

| Placeholder               | JSON Syntax                     |
| ------------------------- | ------------------------------- |
| `{{cookie:session_id}}` | `"\"{{cookie:session_id}}\""` |
| `{{cookie:csrf_token}}` | `"\"{{cookie:csrf_token}}\""` |

### 5. Window Properties

Access JavaScript window object:

| Placeholder                              | JSON Syntax                                    |
| ---------------------------------------- | ---------------------------------------------- |
| `{{windowProperty:location.href}}`     | `"\"{{windowProperty:location.href}}\""`     |
| `{{windowProperty:__CONFIG__.apiKey}}` | `"\"{{windowProperty:__CONFIG__.apiKey}}\""` |

### 6. Meta Tags

Access HTML meta tag content:

| Placeholder             | JSON Syntax                   |
| ----------------------- | ----------------------------- |
| `{{meta:csrf-token}}` | `"\"{{meta:csrf-token}}\""` |
| `{{meta:og:title}}`   | `"\"{{meta:og:title}}\""`   |

### 7. Builtin Parameters

Auto-generated values (no definition needed):

| Placeholder                | JSON Syntax                      | Resolves To                                |
| -------------------------- | -------------------------------- | ------------------------------------------ |
| `{{uuid}}`               | `"\"{{uuid}}\""`               | `"550e8400-e29b-41d4-a716-446655440000"` |
| `{{epoch_milliseconds}}` | `"\"{{epoch_milliseconds}}\""` | `"1704067200000"`                        |

---

## Complete Examples

### Example 1: Request Body with Mixed Types

```json
{
  "body": {
    "username": "\"{{username}}\"",
    "email": "\"{{email}}\"",
    "age": "{{age}}",
    "limit": "{{limit}}",
    "active": "{{is_active}}",
    "token": "\"{{sessionStorage:session.token}}\""
  }
}
```

Resolves to:

```json
{
  "body": {
    "username": "john",
    "email": "john@example.com",
    "age": 25,
    "limit": 100,
    "active": true,
    "token": "eyJhbGciOiJIUzI1NiIs..."
  }
}
```

### Example 2: URL with Path Parameters

```json
{
  "url": "https://api.example.com/users/\"{{user_id}}\"/posts"
}
```

Resolves to:

```json
{
  "url": "https://api.example.com/users/123/posts"
}
```

### Example 3: Headers

```json
{
  "headers": {
    "Authorization": "Bearer \"{{sessionStorage:auth.access_token}}\"",
    "X-CSRF-Token": "\"{{cookie:csrf_token}}\"",
    "X-Request-ID": "\"{{uuid}}\"",
    "Content-Type": "application/json"
  }
}
```

### Example 4: Chained Operations

Operation 1 stores auth response:

```json
{
  "type": "fetch",
  "endpoint": { "url": "https://api.example.com/auth" },
  "session_storage_key": "auth_response"
}
```

Operation 2 uses the stored token:

```json
{
  "type": "fetch",
  "endpoint": {
    "url": "https://api.example.com/data",
    "headers": {
      "Authorization": "Bearer \"{{sessionStorage:auth_response.token}}\""
    }
  }
}
```

---

## Nested Path Access

Use dot notation for nested objects:

```
{{sessionStorage:response.data.user.profile.name}}
```

For arrays, use numeric indices:

```
{{sessionStorage:results.items.0.id}}
{{sessionStorage:results.items.0.attributes.name}}
```

---

## Quick Reference Table

| Scenario         | JSON Syntax                                      | Result                |
| ---------------- | ------------------------------------------------ | --------------------- |
| String param     | `"name": "\"{{username}}\""`                   | `"name": "john"`    |
| Number param     | `"count": "{{limit}}"`                         | `"count": 50`       |
| Bool param       | `"active": "{{is_active}}"`                    | `"active": true`    |
| String in URL    | `"/api/\"{{user_id}}\"/data"`                  | `"/api/123/data"`   |
| Number in string | `"page\"{{num}}\""`                            | `"page5"`           |
| Concatenated     | `"msg_\"{{id}}\""`                             | `"msg_abc"`         |
| Session storage  | `"token": "\"{{sessionStorage:auth.token}}\""` | `"token": "eyJ..."` |
| Cookie           | `"sid": "\"{{cookie:session_id}}\""`           | `"sid": "abc123"`   |

---

## Placeholder Resolution Process

1. **Extract** - Find all `{{...}}` patterns in the string
2. **Categorize** - Determine source type (parameter, storage, builtin)
3. **Resolve** - Fetch actual value from source at runtime
4. **Substitute** - Replace placeholder with resolved value
5. **Parse** - Strip outer quotes for primitives, keep for strings
