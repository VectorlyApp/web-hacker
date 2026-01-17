# Execution

> Execution context, result structure, CDP sessions, session storage chaining. Error handling reference.

Execution involves running a routine against a browser instance via Chrome DevTools Protocol (CDP).

## Execution Context

The `RoutineExecutionContext` maintains state during execution:

```python
class RoutineExecutionContext:
    session_id: str                    # CDP session ID
    ws: WebSocket                      # Browser connection
    send_cmd: Callable                 # Send CDP command
    recv_until: Callable               # Receive CDP response
    parameters_dict: dict              # User parameters
    timeout: float                     # Operation timeout (default: 180s)
    current_url: str                   # Current page URL
    result: RoutineExecutionResult     # Accumulating result
    current_operation_metadata: ...    # Current operation metadata
```

## Execution Result

```python
class RoutineExecutionResult:
    ok: bool                           # Success flag
    error: str | None                  # Error message
    warnings: list[str]                # Warning messages
    operations_metadata: list[...]     # Per-operation metadata
    placeholder_resolution: dict       # Resolved placeholder values
    is_base64: bool                    # Is data base64-encoded?
    content_type: MimeType | str       # MIME type of data
    filename: str | None               # Suggested filename
    data: dict | list | str | None     # Result data
```

## Operation Metadata

Each operation records:

```python
class OperationExecutionMetadata:
    type: str                          # Operation type
    duration_seconds: float            # Execution time
    details: dict                      # Operation-specific data
    error: str | None                  # Error if failed
```

## Execution Flow

### 1. Setup Phase
```
Routine.execute(parameters)
    │
    ├─ Validate parameters
    ├─ Create/attach to browser tab
    │   ├─ Create target (incognito or regular)
    │   └─ Attach with flatten=True
    └─ Enable CDP domains
        ├─ Page.enable
        ├─ Runtime.enable
        ├─ Network.enable
        └─ DOM.enable
```

### 2. Operation Phase
```
For each operation:
    │
    ├─ Create operation metadata
    ├─ Interpolate parameters
    │   └─ Replace {{param}} with actual values
    ├─ Execute operation
    │   └─ CDP commands via WebSocket
    ├─ Collect results
    │   ├─ Store in sessionStorage if requested
    │   └─ Update metadata
    └─ Handle errors
        ├─ Log error
        └─ Update result.ok = False
```

### 3. Cleanup Phase
```
    ├─ Parse final result
    │   ├─ Try JSON parse
    │   └─ Try Python literal_eval
    ├─ Close browser tab
    └─ Return RoutineExecutionResult
```

## CDP Session Types

### Flattened Session
```python
Target.attachToTarget(targetId=..., flatten=True)
```
- Returns `sessionId` for multiplexing
- All commands include `sessionId` parameter
- Recommended for routine execution

### Direct WebSocket
- Connect directly to page's WebSocket URL
- Simpler but doesn't support multiplexing
- Used for monitoring

## Session Storage Pattern

Operations chain data through browser sessionStorage:

```
Operation 1 (fetch):
    → Store response in sessionStorage["step1_result"]

Operation 2 (fetch):
    → Read {{sessionStorage:step1_result.token}}
    → Store response in sessionStorage["step2_result"]

Operation 3 (return):
    → Retrieve sessionStorage["step2_result"]
    → Return as final result
```

## Chunked Data Transfer

Large data (>256KB) is transferred in chunks:

```python
# Writing to sessionStorage
for chunk in chunks(data, 256_000):
    Runtime.evaluate(
        expression=f'sessionStorage.setItem("{key}", sessionStorage.getItem("{key}") + {json.dumps(chunk)})'
    )

# Reading from sessionStorage
while True:
    chunk = Runtime.evaluate(
        expression=f'sessionStorage.getItem("{key}").substring({offset}, {offset + 256_000})'
    )
    if not chunk:
        break
    result += chunk
```

## Error Handling

### Operation Errors
- Logged to `result.error`
- `result.ok = False`
- Execution continues (unless critical)

### Timeout Errors
- Default timeout: 180 seconds
- Per-operation timeouts (e.g., `timeout_ms: 20000`)
- Raises exception on timeout

### Validation Errors
- Parameter validation before execution
- Placeholder validation during interpolation
- JSON parsing validation for results

## Example Execution

```python
from web_hacker import Routine

routine = Routine.model_validate_json(routine_json)

result = routine.execute(
    parameters={
        "origin": "BOS",
        "destination": "NYP",
        "date": "2026-08-22"
    },
    debugging_address="127.0.0.1:9222",
    timeout=300.0
)

if result.ok:
    print(result.data)
else:
    print(f"Error: {result.error}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
```
