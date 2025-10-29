# web-hacker

Reverse engineer any web app!

## Prerequisits

## Setup Your Environment

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


## Monitor Browser While Performing Some Task


## Run Routine Discovery Pipeline