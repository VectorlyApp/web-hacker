# Examples

> Real-world examples: arXiv download, Polymarket API, MA corp search, Amtrak multi-step chain.

Real-world routine examples from the codebase.

## 1. Simple Download (arXiv PDF)

Download a paper from arXiv by ID.

### Routine
```json
{
  "name": "download_arxiv_paper",
  "description": "Download a paper PDF from arXiv",
  "incognito": true,
  "parameters": [
    {
      "name": "paper_id",
      "type": "string",
      "required": true,
      "description": "arXiv paper ID (e.g., 1706.03762)",
      "examples": ["1706.03762"],
      "min_length": 1,
      "max_length": 200
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

### Input
```json
{
  "paper_id": "1706.03762"
}
```

### Output
Base64-encoded PDF with metadata:
```json
{
  "data": "JVBERi0xLjQK...",
  "content_type": "application/pdf",
  "filename": "1706.03762.pdf",
  "is_base64": true
}
```

---

## 2. API Query (Polymarket)

Fetch betting markets from Polymarket API.

### Routine
```json
{
  "name": "get_polymarket_bets",
  "description": "Fetch newest betting events from Polymarket",
  "incognito": true,
  "parameters": [
    {
      "name": "limit",
      "type": "integer",
      "required": false,
      "default": 20,
      "min_value": 1,
      "max_value": 100,
      "description": "Number of events to fetch"
    },
    {
      "name": "offset",
      "type": "integer",
      "required": false,
      "default": 0,
      "min_value": 0,
      "description": "Pagination offset"
    }
  ],
  "operations": [
    {
      "type": "navigate",
      "url": "https://polymarket.com",
      "sleep_after_navigation_seconds": 2.0
    },
    {
      "type": "fetch",
      "endpoint": {
        "url": "https://gamma-api.polymarket.com/events/pagination?limit=\"{{limit}}\"&active=true&archived=false&closed=false&order=startDate&ascending=false&offset=\"{{offset}}\"",
        "method": "GET",
        "credentials": "omit"
      },
      "session_storage_key": "polymarket_events"
    },
    {
      "type": "return",
      "session_storage_key": "polymarket_events"
    }
  ]
}
```

### Input
```json
{
  "limit": 10,
  "offset": 0
}
```

---

## 3. UI Automation (Massachusetts Corp Search)

Search for corporations with form interaction.

### Routine
```json
{
  "name": "massachusetts_corp_search",
  "description": "Search MA corporation database",
  "incognito": true,
  "parameters": [
    {
      "name": "entity_name",
      "type": "string",
      "required": true,
      "description": "Corporation name to search"
    }
  ],
  "operations": [
    {
      "type": "navigate",
      "url": "https://corp.sec.state.ma.us/CorpWeb/CorpSearch/CorpSearch.aspx",
      "sleep_after_navigation_seconds": 3.0
    },
    {
      "type": "scroll",
      "delta_y": 300,
      "behavior": "smooth"
    },
    {
      "type": "click",
      "selector": "#MainContent_txtEntityName"
    },
    {
      "type": "input_text",
      "selector": "#MainContent_txtEntityName",
      "text": "\"{{entity_name}}\"",
      "clear": true
    },
    {
      "type": "press",
      "key": "arrowdown"
    },
    {
      "type": "sleep",
      "timeout_seconds": 0.5
    },
    {
      "type": "click",
      "selector": "#MainContent_btnSearch"
    },
    {
      "type": "wait_for_url",
      "url_regex": ".*CorpSearchResults.*",
      "timeout_ms": 20000
    },
    {
      "type": "js_evaluate",
      "js": "(()=>{const table=document.getElementById('MainContent_SearchControl_grdSearchResultsEntity');if(!table)return{error:'Table not found',results:[]};const rows=table.querySelectorAll('tr.GridRow');const results=[];for(const row of rows){const cells=row.querySelectorAll('td,th');results.push({entity_name:cells[0]?.textContent?.trim()||'',id_number:cells[1]?.textContent?.trim()||'',address:cells[3]?.textContent?.trim().replace(/\\s+/g,' ')||''});}return{results,count:results.length};})()",
      "session_storage_key": "corp_search_results"
    },
    {
      "type": "return",
      "session_storage_key": "corp_search_results"
    }
  ]
}
```

---

## 4. Multi-Step API Chain (Amtrak)

Complex routine with dependent API calls.

### Key Patterns

#### Autocomplete → Search Chain
```json
[
  {
    "type": "fetch",
    "endpoint": {
      "url": "https://www.amtrak.com/services/AutoCompleter?searchTerm=\"{{origin}}\"",
      "method": "GET"
    },
    "session_storage_key": "autocomplete_origin"
  },
  {
    "type": "fetch",
    "endpoint": {
      "url": "https://www.amtrak.com/services/Search",
      "method": "POST",
      "body": {
        "origin": {
          "code": "\"{{sessionStorage:autocomplete_origin.autoCompleteList.0.stationCode}}\""
        }
      }
    },
    "session_storage_key": "search_results"
  }
]
```

#### Dynamic Headers from Session
```json
{
  "headers": {
    "x-amtrak-trace-id": "\"{{sessionStorage:ibsession.sessionid}}\"",
    "x-amtrak-product-source": "mobile"
  }
}
```

#### Nested Path Access
```json
{
  "body": {
    "origin": {
      "code": "\"{{sessionStorage:autocomplete_origin.autoCompleteList.0.stationCode}}\"",
      "name": "\"{{sessionStorage:autocomplete_origin.autoCompleteList.0.stationName}}\""
    }
  }
}
```

---

## Common Patterns

### 1. Navigate + Fetch + Return
```json
[
  {"type": "navigate", "url": "https://example.com"},
  {"type": "fetch", "endpoint": {...}, "session_storage_key": "result"},
  {"type": "return", "session_storage_key": "result"}
]
```

### 2. Form Fill + Submit
```json
[
  {"type": "click", "selector": "input[name='search']"},
  {"type": "input_text", "selector": "input[name='search']", "text": "\"{{query}}\""},
  {"type": "press", "key": "enter"},
  {"type": "wait_for_selector", "selector": ".results"}
]
```

### 3. Auth Token Flow
```json
[
  {"type": "fetch", "endpoint": {"url": "/auth"}, "session_storage_key": "auth"},
  {"type": "fetch", "endpoint": {
    "url": "/api/data",
    "headers": {"Authorization": "Bearer \"{{sessionStorage:auth.token}}\""}
  }}
]
```

### 4. JavaScript Extraction
```json
{
  "type": "js_evaluate",
  "js": "(()=>{return Array.from(document.querySelectorAll('.item')).map(el=>({title:el.querySelector('.title')?.textContent,price:el.querySelector('.price')?.textContent}))})()"
}
```
