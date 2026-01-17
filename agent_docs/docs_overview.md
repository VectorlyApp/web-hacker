# Web Hacker Overview

> Architecture and workflow: monitor browser → discover routines → execute. Core components and file structure.

Web Hacker is a browser automation framework that uses AI to discover and generate executable routines from browser activity.

## Architecture

```
Browser Monitoring → Routine Discovery → Routine Execution
     (CDP)              (AI-Powered)         (CDP-Based)
```

## Core Workflow

### 1. Monitor Phase
- Chrome runs with `--remote-debugging-address=127.0.0.1:9222`
- BrowserMonitor connects via WebSocket
- Captures: network transactions, storage events, user interactions, window properties
- Outputs consolidated JSON files

### 2. Discovery Phase
- LocalContextManager parses captured data
- Creates OpenAI vectorstore for LLM search
- RoutineDiscoveryAgent iteratively:
  - Identifies relevant transactions
  - Extracts variables (static, dynamic tokens, parameters)
  - Resolves variable sources (storage, window props, prior responses)
  - Constructs and productionizes routine

### 3. Execution Phase
- Routine creates/attaches to Chrome tab via CDP
- Executes operations sequentially
- Interpolates parameters and resolves placeholders
- Returns structured result data

## Key Components

| Component | Purpose |
|-----------|---------|
| `WebHacker` | Main SDK facade |
| `BrowserMonitor` | CDP-based activity capture |
| `RoutineDiscoveryAgent` | AI-powered routine generation |
| `Routine` | Executable automation spec |
| `RoutineExecutionContext` | Runtime state during execution |

## File Structure

```
web_hacker/
├── sdk/
│   ├── client.py         # WebHacker facade
│   ├── monitor.py        # BrowserMonitor
│   ├── discovery.py      # RoutineDiscovery wrapper
│   └── execution.py      # RoutineExecutor wrapper
├── routine_discovery/
│   ├── agent.py          # RoutineDiscoveryAgent
│   └── context_manager.py # LocalContextManager
├── data_models/routine/
│   ├── routine.py        # Routine model
│   ├── operation.py      # Operation types
│   ├── parameter.py      # Parameter definitions
│   ├── placeholder.py    # Placeholder resolution
│   ├── endpoint.py       # HTTP endpoint model
│   └── execution.py      # Execution context/result
└── cdp/
    ├── cdp_session.py    # CDP session coordinator
    └── *_monitor.py      # Specialized monitors
```

## Usage Example

```python
from web_hacker import WebHacker

hacker = WebHacker(openai_api_key="sk-...")

# 1. Monitor browser activity
with hacker.monitor_browser(output_dir="./captures"):
    # User performs actions in browser
    pass

# 2. Discover routine from captures
result = hacker.discover_routine(
    task="Search for trains from Boston to NYC",
    cdp_captures_dir="./captures"
)

# 3. Execute routine with parameters
execution = hacker.execute_routine(
    routine=result.routine,
    parameters={"origin": "BOS", "destination": "NYP"}
)

print(execution.data)  # Structured results
```
