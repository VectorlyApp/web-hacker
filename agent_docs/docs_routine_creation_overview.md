# Routine Creation Overview

> 8-step process to create routines from CDP captures: identify → extract → resolve → construct.

Create a routine from CDP browser session captures.

## Prerequisites

1. **CDP Captures** - Network transactions and storage data from browser session
2. **Task Description** - What the routine should accomplish
3. **Vectorstore** - Captures loaded for LLM search

## Creation Steps

### Step 1: Load Captures

Load into vectorstore:
- Network transactions (requests + responses)
- Storage (cookies, localStorage, sessionStorage)
- Window properties
- Meta tags

### Step 2: Identify Target Transaction

Find the network transaction that accomplishes the user's task.

Input: Task description + list of transaction IDs
Output: Single transaction ID

### Step 3: Confirm Transaction

Verify the transaction matches user intent by examining full request/response.
If wrong, retry Step 2 with feedback.

### Step 4: Extract Variables

Analyze the request for dynamic values:

| Type | Description | Example |
|------|-------------|---------|
| PARAMETER | User input | search query, page number |
| DYNAMIC_TOKEN | Session tokens | CSRF, auth token, trace ID |
| STATIC_VALUE | Hardcode these | app version, client name |

### Step 5: Resolve Dynamic Variables

For each DYNAMIC_TOKEN, find its source:

1. Check storage (sessionStorage, localStorage, cookies)
2. Check window properties
3. Check previous transaction responses
4. If not found, hardcode the observed value

If found in previous transaction → that transaction becomes a dependency.

### Step 6: Process Dependencies

Use BFS to process all dependency transactions:
1. Add dependency to queue
2. Repeat Steps 4-5 for each dependency
3. Continue until queue empty

Result: Ordered list (dependencies first → target last)

### Step 7: Construct Routine

Build operations in order:
1. Navigate to target page
2. Sleep 2-3 seconds (let JS populate storage)
3. Fetch operations for each transaction
4. Return final result

Rules:
- Each fetch stores result in sessionStorage
- Chain fetches via `"\"{{sessionStorage:key.path}}\""`
- Minimize parameters (only user-provided values)
- Hardcode unresolved variables

### Step 8: Validate

Check:
- All parameters used
- No undefined placeholders
- Valid JSON
- Correct quote format (`"\"{{param}}\""` for strings)

If validation fails, retry Step 7.

Output: Routine ready for execution

## Key Concepts

**Transaction Dependencies**: A transaction depends on another if it uses a value from that transaction's response. Execute dependencies first.

**Resolution Priority**:
1. Transaction response (creates dependency)
2. sessionStorage/localStorage
3. Window property
4. Hardcode (fallback)

**Minimal Parameters**: Only create parameters for values the user explicitly provides. Hardcode everything else.
