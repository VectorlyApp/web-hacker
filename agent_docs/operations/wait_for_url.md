# wait_for_url Operation

> Wait for URL to match a regex pattern. Use after form submissions, OAuth redirects, or any action that triggers navigation. More reliable than sleep for timing-dependent flows. Polls every 200ms until match or timeout.

Wait for the browser URL to match a regex pattern. Useful for waiting after navigation triggers (form submissions, redirects, OAuth flows).

## Basic Format

```json
{
  "type": "wait_for_url",
  "url_regex": ".*\\/dashboard.*",
  "timeout_ms": 20000
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"wait_for_url"` |
| `url_regex` | string | Yes | - | Regex pattern to match against URL |
| `timeout_ms` | int | No | `20000` | Max wait time in milliseconds |

## How It Works

1. **Polls URL** - Checks `window.location.href` every 200ms
2. **Tests regex** - Matches current URL against pattern
3. **Returns on match** - Continues routine when URL matches
4. **Timeout error** - Throws error if no match within timeout

## Examples

### Wait for Dashboard After Login
```json
[
  {
    "type": "click",
    "selector": "button[type='submit']"
  },
  {
    "type": "wait_for_url",
    "url_regex": ".*/dashboard.*"
  }
]
```

### Wait for Search Results
```json
[
  {
    "type": "input_text",
    "selector": "input[name='q']",
    "text": "{{query}}"
  },
  {
    "type": "press",
    "key": "enter"
  },
  {
    "type": "wait_for_url",
    "url_regex": ".*search\\?.*q=.*"
  }
]
```

### Wait for OAuth Callback
```json
[
  {
    "type": "click",
    "selector": ".oauth-login-btn"
  },
  {
    "type": "wait_for_url",
    "url_regex": ".*/callback.*code=.*",
    "timeout_ms": 60000
  }
]
```

### Wait for Specific Page
```json
{
  "type": "wait_for_url",
  "url_regex": "^https://example\\.com/success$"
}
```

### Wait for Any URL Change
```json
{
  "type": "wait_for_url",
  "url_regex": "^(?!https://example\\.com/login).*$"
}
```
(Matches any URL that's NOT the login page)

## Common Regex Patterns

| Pattern | Matches |
|---------|---------|
| `.*dashboard.*` | URLs containing "dashboard" |
| `.*\\/success$` | URLs ending with "/success" |
| `.*\\?code=.*` | URLs with "code=" query param |
| `^https://example\\.com/.*` | Any path on example.com |
| `.*#token=.*` | URLs with hash fragment containing "token=" |

## Regex Tips

1. **Escape special chars** - Use `\\.` for literal dots, `\\/` for slashes
2. **Anchors** - Use `^` for start, `$` for end
3. **Wildcards** - `.*` matches any characters
4. **Optional** - `?` makes preceding char optional
5. **JSON escaping** - Remember to double-escape: `\\` in JSON becomes `\` in regex

## When to Use

- After form submission that triggers redirect
- After clicking link that causes navigation
- OAuth/SSO flows with redirects
- Single-page apps with URL routing
- Waiting for page to fully load (URL changes)

## vs sleep Operation

| Approach | Pros | Cons |
|----------|------|------|
| `wait_for_url` | Precise, continues immediately when ready | Requires knowing URL pattern |
| `sleep` | Simple, always works | May wait too long or not long enough |

Prefer `wait_for_url` when you know the expected URL pattern.

## Error Handling

If timeout is reached without a match:
```
RuntimeError: Timeout waiting for URL to match pattern '...'
Current URL: https://example.com/current-page
```

The error includes the current URL to help debug why the pattern didn't match.
