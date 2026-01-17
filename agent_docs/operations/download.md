# download Operation

> Download binary files (PDFs, images, audio, video, Excel, Word docs) and return as base64-encoded data. Supports authenticated downloads with headers and cookies. Usually the final operation when the routine's goal is to retrieve a file.

Download binary files (PDFs, images, audio, etc.) and return them as base64-encoded data.

## Basic Format

```json
{
  "type": "download",
  "endpoint": {
    "url": "https://example.com/file.pdf",
    "method": "GET",
    "headers": {},
    "credentials": "include"
  },
  "filename": "report.pdf"
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | - | Must be `"download"` |
| `endpoint` | object | Yes | - | Request configuration (same as fetch) |
| `filename` | string | Yes | - | Filename for the downloaded file |

### Endpoint Object

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | Yes | - | URL of the file to download |
| `method` | string | No | `"GET"` | HTTP method |
| `headers` | object | No | `{}` | Request headers |
| `body` | any | No | `null` | Request body (if POST) |
| `credentials` | string | No | `"include"` | Cookie handling |

## Return Value

The download operation sets the routine result directly with:

| Field | Description |
|-------|-------------|
| `data` | Base64-encoded file content |
| `is_base64` | `true` |
| `content_type` | MIME type from response (e.g., `"application/pdf"`) |
| `filename` | The filename you specified |

## Examples

### Download PDF
```json
{
  "type": "download",
  "endpoint": {
    "url": "https://example.com/reports/{{report_id}}.pdf",
    "method": "GET"
  },
  "filename": "report_{{report_id}}.pdf"
}
```

### Download with Authentication
```json
{
  "type": "download",
  "endpoint": {
    "url": "https://api.example.com/documents/{{doc_id}}",
    "method": "GET",
    "headers": {
      "Authorization": "Bearer {{sessionStorage:access_token}}"
    }
  },
  "filename": "document.pdf"
}
```

### POST Request Download
Some APIs require POST to generate files:
```json
{
  "type": "download",
  "endpoint": {
    "url": "https://api.example.com/generate-report",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "report_type": "\"{{report_type}}\"",
      "date_range": {
        "start": "\"{{start_date}}\"",
        "end": "\"{{end_date}}\""
      }
    }
  },
  "filename": "report_{{report_type}}.pdf"
}
```

### Download Image
```json
{
  "type": "download",
  "endpoint": {
    "url": "https://example.com/images/{{image_id}}.png",
    "method": "GET"
  },
  "filename": "image_{{image_id}}.png"
}
```

## When to Use download vs fetch

| Use Case | Operation |
|----------|-----------|
| JSON/text API response | `fetch` |
| Binary file (PDF, image, audio, video) | `download` |
| HTML content | `return_html` |

## Important Notes

1. **Typically the last operation** - Download sets `result.data` directly, so it's usually the final operation in a routine.

2. **Large files** - Downloads are chunked (256KB chunks) to handle large files without memory issues.

3. **Placeholders work** - You can use `{{param}}` in URL, headers, body, and filename.

4. **Base64 output** - The result is base64-encoded. Decode it to get the original binary data.

## Common File Types

| Extension | Content-Type |
|-----------|--------------|
| `.pdf` | `application/pdf` |
| `.png` | `image/png` |
| `.jpg` | `image/jpeg` |
| `.gif` | `image/gif` |
| `.mp3` | `audio/mpeg` |
| `.mp4` | `video/mp4` |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.zip` | `application/zip` |
