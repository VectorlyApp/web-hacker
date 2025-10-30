# web-hacker

Reverse engineer any web app!

## Prerequisits
 - Python 3.11+
 - Google Chrome (stable)
 - uv (Python package manager)
   - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex`
 - OpenAI API key
## Setup Your Environment
```bash
# 1) Clone and enter the repo
git clone <repo-url>
cd web-hacker

# 2) Create & activate virtual environment (uv)
uv venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate

# 3) Install in editable mode via uv (pip-compatible interface)
uv pip install -e .

# 4) Configure environment
cp .env.example .env  # then edit values
# or set directly
export OPENAI_API_KEY="sk-..."

# 5) Smoke test
python -c "import src; print('env ok')"
```

## Launch Chrome in Debug Mode

### Instructions for MacOS

```
# Create temporary chrome user directory
mkdir $HOME/tmp
mkdir $HOME/tmp/chrome

# Launch Chrome app in debug mode (this exposes websocket for controlling and monitoring the browser)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/tmp/chrome" \
  '--remote-allow-origins=*' \
  --no-first-run \
  --no-default-browser-check


# Verify chrome is running in debug mode
curl http://127.0.0.1:9222/json/version

# You should see something like this:
{
   "Browser": "Chrome/141.0.7390.123",
   "Protocol-Version": "1.3",
   "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
   "V8-Version": "14.1.146.11",
   "WebKit-Version": "537.36 (@**********************************)",
   "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/*************************************"
}
```

### Instructions for Windows

## Monitor Browser While Performing Some Task

## Run Routine Discovery Pipeline
