#!/bin/bash
# Quickstart script: Full workflow for web-hacker
# This script guides you through: Launch Chrome → Monitor → Discover → Execute

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PORT=9222
OUTPUT_DIR="./cdp_captures"
ROUTINE_OUTPUT="./routine_discovery_output"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Web Hacker - Quickstart Workflow                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Launch Chrome
echo -e "${GREEN}Step 1: Launching Chrome in debug mode...${NC}"

CHROME_USER_DIR="$HOME/tmp/chrome"
mkdir -p "$CHROME_USER_DIR"

# Detect Chrome path
if [[ "$OSTYPE" == "darwin"* ]]; then
    CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CHROME_PATH=$(which google-chrome 2>/dev/null || which chromium-browser 2>/dev/null || which chromium 2>/dev/null)
else
    CHROME_PATH=""
fi

# Check if Chrome is already running
if curl -s "http://127.0.0.1:$PORT/json/version" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome is already running in debug mode on port $PORT${NC}"
else
    # Try to launch Chrome
    CHROME_FOUND=false
    if [[ "$OSTYPE" == "darwin"* ]] && [[ -f "$CHROME_PATH" ]]; then
        CHROME_FOUND=true
    elif [[ "$OSTYPE" == "linux-gnu"* ]] && command -v "$CHROME_PATH" > /dev/null 2>&1; then
        CHROME_FOUND=true
    fi
    
    if [[ "$CHROME_FOUND" == "true" ]]; then
        echo "🚀 Launching Chrome..."
        "$CHROME_PATH" \
          --remote-debugging-address=127.0.0.1 \
          --remote-debugging-port=$PORT \
          --user-data-dir="$CHROME_USER_DIR" \
          --remote-allow-origins=* \
          --no-first-run \
          --no-default-browser-check \
          > /dev/null 2>&1 &
        
        CHROME_PID=$!
        
        # Wait for Chrome to be ready
        echo "⏳ Waiting for Chrome to start..."
        for i in {1..10}; do
            if curl -s "http://127.0.0.1:$PORT/json/version" > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Chrome is ready!${NC}"
                break
            fi
            sleep 1
        done
        
        if ! curl -s "http://127.0.0.1:$PORT/json/version" > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Chrome failed to start automatically.${NC}"
            kill $CHROME_PID 2>/dev/null || true
            echo "   Please launch Chrome manually with:"
            echo "   --remote-debugging-port=$PORT"
            echo ""
            read -p "Press Enter when Chrome is running in debug mode..."
        fi
    else
        echo -e "${YELLOW}⚠️  Chrome not found automatically.${NC}"
        echo "   Please launch Chrome manually with:"
        echo "   --remote-debugging-port=$PORT"
        echo ""
        read -p "Press Enter when Chrome is running in debug mode..."
    fi
fi

echo ""

# Step 2: Monitor
echo -e "${GREEN}Step 2: Starting browser monitoring...${NC}"
echo -e "${YELLOW}📋 Instructions:${NC}"
echo "   1. A new Chrome tab will open"
echo "   2. Navigate to your target website"
echo "   3. Perform the actions you want to automate (search, login, etc.)"
echo "   4. Press Ctrl+C when you're done"
echo ""
read -p "Press Enter to start monitoring..."

echo ""
echo "🚀 Starting monitor (press Ctrl+C when done)..."
web-hacker-monitor \
  --host 127.0.0.1 \
  --port $PORT \
  --output-dir "$OUTPUT_DIR" \
  --url about:blank \
  --incognito || {
    echo ""
    echo -e "${YELLOW}⚠️  Monitoring stopped.${NC}"
}

echo ""

# Step 3: Discover
if [[ ! -d "$OUTPUT_DIR" ]] || [[ -z "$(ls -A $OUTPUT_DIR/network/transactions 2>/dev/null)" ]]; then
    echo -e "${YELLOW}⚠️  No capture data found. Skipping discovery step.${NC}"
    echo "   Make sure you performed actions during monitoring."
    exit 0
fi

echo -e "${GREEN}Step 3: Discovering routine from captured data...${NC}"
echo -e "${YELLOW}📋 Enter a description of what you want to automate:${NC}"
echo "   Example: 'Search for flights and get prices'"
read -p "   Task: " TASK

if [[ -z "$TASK" ]]; then
    echo -e "${YELLOW}⚠️  No task provided. Skipping discovery.${NC}"
    exit 0
fi

echo ""
echo "🤖 Running routine discovery agent..."
web-hacker-discover \
  --task "$TASK" \
  --cdp-captures-dir "$OUTPUT_DIR" \
  --output-dir "$ROUTINE_OUTPUT" \
  --llm-model gpt-5

echo ""

# Step 4: Execute (optional)
if [[ ! -f "$ROUTINE_OUTPUT/routine.json" ]]; then
    echo -e "${YELLOW}⚠️  Routine not found at $ROUTINE_OUTPUT/routine.json${NC}"
    exit 0
fi

echo -e "${GREEN}Step 4: Ready to execute routine!${NC}"
echo ""
echo "✅ Routine discovered successfully!"
echo "   Location: $ROUTINE_OUTPUT/routine.json"
echo ""
echo -e "${YELLOW}To execute the routine, run:${NC}"
echo "   web-hacker-execute \\"
echo "     --routine-path $ROUTINE_OUTPUT/routine.json \\"
if [[ -f "$ROUTINE_OUTPUT/test_parameters.json" ]]; then
    echo "     --parameters-path $ROUTINE_OUTPUT/test_parameters.json"
else
    echo "     --parameters-dict '{\"param1\": \"value1\", \"param2\": \"value2\"}'"
fi
echo ""
echo -e "${BLUE}💡 Tip: Review $ROUTINE_OUTPUT/routine.json before executing${NC}"

