import json
import time
import os
import sys
import logging
import websocket
import requests
import threading

# Ensure we can import from web_hacker
sys.path.append(os.getcwd())

try:
    from web_hacker.cdp.tab_managements import cdp_new_tab
except ImportError:
    print("Could not import web_hacker modules. Make sure you are in the project root.")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("replay")

def replay_interactions(file_path):
    logger.info(f"Loading interactions from {file_path}")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("File not found.")
        return

    interactions = data.get("interactions", [])
    if not interactions:
        logger.info("No interactions found.")
        return

    # Filter out spammy mouse_over/move events for clarity and speed, 
    # unless you want full fidelity (can be very slow).
    # Keeping: click, mouse_down/up, key_*, input
    # Actually, we'll just process them and skip types we don't handle.
    
    # Sort by timestamp
    interactions.sort(key=lambda x: x.get("timestamp", 0))

    # Create Tab
    try:
        target_id, context_id = cdp_new_tab(url="about:blank")
        logger.info(f"Created tab: {target_id}")
    except Exception as e:
        logger.error(f"Failed to create tab. Is Chrome running on port 9222? Error: {e}")
        return

    # Connect to the tab
    ws_url = f"ws://127.0.0.1:9222/devtools/page/{target_id}"
    ws = websocket.create_connection(ws_url)
    
    ws_lock = threading.Lock()

    def send_safe(msg):
        with ws_lock:
            try:
                ws.send(msg)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

    # Monitor for dialogs (alerts, beforeunload) and auto-accept them
    # def monitor_dialogs():
    #     while True:
    #         try:
    #             # This blocks until a message is received
    #             msg = ws.recv()
    #             if not msg: 
    #                 break
    #             
    #             data = json.loads(msg)
    #             method = data.get("method")
    #             
    #             if method == "Page.javascriptDialogOpening":
    #                 dialog_type = data.get("params", {}).get("type")
    #                 msg_text = data.get("params", {}).get("message")
    #                 logger.info(f"Dialog detected ({dialog_type}): {msg_text} - Auto-accepting to leave/proceed.")
    #                 
    #                 # Handle the dialog immediately
    #                 send_safe(json.dumps({
    #                     "id": 999999, 
    #                     "method": "Page.handleJavaScriptDialog", 
    #                     "params": {"accept": True}
    #                 }))
    #                 
    #         except Exception as e:
    #             # Socket might be closed or other error
    #             break
    # 
    # dialog_thread = threading.Thread(target=monitor_dialogs, daemon=True)
    # dialog_thread.start()

    
    # Counter for command IDs
    _cmd_id = 0
    def send(method, params=None):
        nonlocal _cmd_id
        _cmd_id += 1
        msg = json.dumps({"id": _cmd_id, "method": method, "params": params or {}})
        send_safe(msg)
        # Fire and forget for speed, unless we need to wait (handled manually)
        return _cmd_id

    def send_and_wait(method, params=None):
        nonlocal _cmd_id
        _cmd_id += 1
        current_id = _cmd_id
        msg = json.dumps({"id": current_id, "method": method, "params": params or {}})
        
        response = {}
        done = threading.Event()
        
        def wait_for_resp():
            while not done.is_set():
                try:
                    # This is tricky because we are already reading in monitor_dialogs
                    # and also dispatching freely. We can't easily intercept responses 
                    # with the current "fire and forget" architecture without refactoring
                    # the whole websocket handling to be event-driven.
                    #
                    # HACK: We'll assume for now we can't easily get the response 
                    # because we don't have a proper listener loop.
                    # BUT, for Runtime.evaluate used below, we REALLY need the result.
                    pass 
                except:
                    pass
        
        # REFACTOR: We need a proper read loop to handle responses if we want to wait.
        # Since the user asked for a simple script, we can't easily architect a full async client here.
        #
        # Alternative: Use a separate synchronous check.
        # The current `monitor_dialogs` thread steals the reads.
        #
        # We will STOP `monitor_dialogs` from stealing ALL messages, or make it smarter.
        # But `monitor_dialogs` is just `ws.recv()` in a loop.
        #
        # Let's make a simple "check visibility" function that injects JS and assumes it works, 
        # or - since we need the return value - we have to modify the read loop.
        pass

    # MODIFIED ARCHITECTURE: Single Reader Thread that dispatches results
    responses = {}
    response_events = {}
    
    def reader_thread():
        while True:
            try:
                message = ws.recv()
                if not message: break
                data = json.loads(message)
                
                # Handle Dialogs
                if data.get("method") == "Page.javascriptDialogOpening":
                    dialog_type = data.get("params", {}).get("type")
                    msg_text = data.get("params", {}).get("message")
                    logger.info(f"Dialog detected ({dialog_type}): {msg_text} - Auto-accepting.")
                    send_safe(json.dumps({
                        "id": 999999, 
                        "method": "Page.handleJavaScriptDialog", 
                        "params": {"accept": True}
                    }))
                    continue
                
                # Handle Command Responses
                if "id" in data:
                    cid = data["id"]
                    if cid in response_events:
                        responses[cid] = data
                        response_events[cid].set()
                        
            except Exception as e:
                logger.error(f"Reader error: {e}")
                break

    # Start the unified reader
    t = threading.Thread(target=reader_thread, daemon=True)
    t.start()

    def send_and_return(method, params=None):
        nonlocal _cmd_id
        _cmd_id += 1
        cid = _cmd_id
        
        event = threading.Event()
        response_events[cid] = event
        
        send_safe(json.dumps({"id": cid, "method": method, "params": params or {}}))
        
        if event.wait(timeout=2.0):
            resp = responses.pop(cid, {})
            del response_events[cid]
            return resp.get("result", {})
        else:
            del response_events[cid]
            return None

    # Enable Input/Page domains

    # Enable Input/Page domains
    send("Page.enable")
    send("Input.enable")
    send("Runtime.enable")

    # Initial Navigation - start at the FIRST URL
    first_url = interactions[0].get("url")
    current_url = first_url
    if first_url:
        logger.info(f"Navigating to initial URL: {first_url}")
        send("Page.navigate", {"url": first_url})
        # Wait for some load... simplistic approach
        time.sleep(5)

    start_time = interactions[0].get("timestamp")
    replay_start = time.time() * 1000
    
    current_scroll_x = 0
    current_scroll_y = 0

    logger.info(f"Starting replay of {len(interactions)} events...")
    
    executed_events = []

    for i, interaction in enumerate(interactions):
        itype = interaction.get("type")
        event = interaction.get("event", {})
        ts = interaction.get("timestamp")
        target_url = interaction.get("url")
        
        # 0. Ensure we are on the correct URL for this interaction
        if target_url and target_url != current_url:
            logger.info(f"URL change detected. Navigating to {target_url}")
            send("Page.navigate", {"url": target_url})
            time.sleep(4)  # Wait for load
            current_url = target_url
        
        executed = False

        # 1. Timing Synchronization
        if ts and start_time:
            # target time offset
            target_offset = ts - start_time
            # current actual offset
            current_offset = (time.time() * 1000) - replay_start
            
            wait_ms = target_offset - current_offset
            if wait_ms > 10: # Only sleep if gap is meaningful > 10ms
                time.sleep(wait_ms / 1000.0)

        # 2. Handle Scroll Sync (if coordinates available)
        if "clientX" in event and "pageX" in event:
            cx = event.get("clientX")
            px = event.get("pageX")
            cy = event.get("clientY")
            py = event.get("pageY")
            
            # Some events (e.g. mouseover on weird elements) have null Y coords; skip safely
            if cx is not None and px is not None and cy is not None and py is not None:
                req_scroll_x = int(px - cx)
                req_scroll_y = int(py - cy)
                
                # Threshold to avoid jitter
                if abs(req_scroll_x - current_scroll_x) > 5 or abs(req_scroll_y - current_scroll_y) > 5:
                    send("Runtime.evaluate", {
                        "expression": f"window.scrollTo({req_scroll_x}, {req_scroll_y})"
                    })
                    current_scroll_x = req_scroll_x
                    current_scroll_y = req_scroll_y

        # 3. LIVE ELEMENT RE-CALCULATION (Smart selectors first, then XPath fallback)
        # Instead of using recorded X/Y, we find the element's REAL position now via:
        #  - ID / name / placeholder
        #  - recorded CSS path
        #  - short text via XPath
        #  - FULL recorded XPath (LAST resort)
        if itype in ["mouse_down", "mousedown", "mouse_up", "mouseup", "click", "mouse_click"]:
            el_info = interaction.get("element", {}) or {}
            xpath = el_info.get("xpath")
            if not xpath:
                # If xpath is missing (older capture), we skip for safety
                msg = (
                    f"SKIPPING action #{i} type={itype} url={target_url} "
                    f"because no XPath was recorded. "
                    f"element.path={el_info.get('path')!r} "
                    f"element.text_snippet={(el_info.get('text') or '')[:80]!r} "
                    f"(STRICT MODE: no XPath = no action)."
                )
                logger.warning(msg)
            else:
                # Smart selector logic with XPath as LAST fallback
                tag = (el_info.get("tagName") or "").lower()
                el_id = el_info.get("id") or ""
                placeholder = el_info.get("placeholder") or ""
                name = el_info.get("name") or ""
                text = (el_info.get("text") or "")[:80]
                role = el_info.get("role") or ""
                path = el_info.get("path") or ""

                find_js = f"""
                (function() {{
                    function checkEl(el) {{
                        if (!el) return null;
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        if (rect.width === 0 && rect.height === 0) return null;
                        if (style.display === 'none' || style.visibility === 'hidden') return null;
                        return {{
                            status: 'visible',
                            x: rect.x + (rect.width / 2),
                            y: rect.y + (rect.height / 2)
                        }};
                    }}

                    let el, res;

                    // Strategy 1: ID
                    if ('{el_id}') {{
                        el = document.getElementById('{el_id}');
                        res = checkEl(el);
                        if (res) return res;
                    }}

                    // Strategy 2: Attributes (name / placeholder)
                    if ('{name}' && '{tag}') {{
                        try {{
                            el = document.querySelector('{tag}[name="{name}"]');
                            res = checkEl(el);
                            if (res) return res;
                        }} catch (e) {{}}
                    }}
                    if ('{placeholder}' && '{tag}') {{
                        try {{
                            el = document.querySelector('{tag}[placeholder="{placeholder}"]');
                            res = checkEl(el);
                            if (res) return res;
                        }} catch (e) {{}}
                    }}

                    // Strategy 3: Recorded CSS path (from interaction monitor)
                    if ('{path}') {{
                        try {{
                            el = document.querySelector('{path}');
                            res = checkEl(el);
                            if (res) return res;
                        }} catch (e) {{}}
                    }}

                    // Strategy 4: Text Content via ad-hoc XPath (short snippet only)
                    if ('{text}' && '{tag}' && '{text}'.length < 50) {{
                        const xpText = "//{tag}[contains(normalize-space(.), " + JSON.stringify('{text}'.trim()) + ")]";
                        try {{
                            const rText = document.evaluate(xpText, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                            el = rText.singleNodeValue;
                            res = checkEl(el);
                            if (res) return res;
                        }} catch (e) {{}}
                    }}

                    // Strategy 5: FULL recorded XPath (LAST RESORT)
                    const xpFull = `{xpath}`;
                    try {{
                        const rFull = document.evaluate(xpFull, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                        el = rFull.singleNodeValue;
                        res = checkEl(el);
                        if (res) return res;
                    }} catch (e) {{}}

                    return {{ status: 'not_found' }};
                }})()
                """
                res = send_and_return("Runtime.evaluate", {"expression": find_js, "returnByValue": True})
                result = res.get("result", {}).get("value", {})

                status = result.get("status")

                if status != 'visible':
                    msg = (
                        f"SKIPPING action #{i} type={itype} url={target_url} "
                        f"because XPath={xpath!r} did not resolve to a visible element "
                        f"(status={status!r}). STRICT MODE: Skipping this action."
                    )
                    logger.warning(msg)
                    executed = False
                else:
                    event["clientX"] = result["x"]
                    event["clientY"] = result["y"]
                    logger.info(f"Targeting XPath '{xpath}' at live coordinates: {result['x']}, {result['y']}")
                    executed = True

        # 4. Event Dispatch
        if executed and itype in ["mouse_down", "mousedown", "mouse_up", "mouseup"]:
            # Use the (potentially updated) coordinates
            x = event.get("clientX", 0)
            y = event.get("clientY", 0)
            
            button_map = {0: "left", 1: "middle", 2: "right"}
            button = button_map.get(event.get("button"), "left")
            
            c_type = "mousePressed" if "down" in itype else "mouseReleased"
            
            params = {
                "type": c_type,
                "x": x,
                "y": y,
                "button": button,
                "clickCount": 1
            }
            send("Input.dispatchMouseEvent", params)
            executed = True

        elif itype in ["key_down", "keydown", "key_up", "keyup"]:
            c_type = "keyDown" if "down" in itype else "keyUp"
            key = event.get("key", "")
            code = event.get("code", "")
            
            # Filter out unknown keys or problematic ones if needed
            params = {
                "type": c_type,
                "key": key,
                "code": code,
                "windowsVirtualKeyCode": event.get("keyCode", 0)
            }
            
            if c_type == "keyDown" and len(key) == 1:
                params["text"] = key
                params["unmodifiedText"] = key
                
            send("Input.dispatchKeyEvent", params)
            executed = True
            
        # Ignore 'click', 'mouse_click' (synthetic)
        # Ignore 'mouse_over' (spammy)
        
        if executed:
            # Add replay timestamp
            interaction_copy = interaction.copy()
            interaction_copy["replay_timestamp"] = time.time() * 1000
            executed_events.append(interaction_copy)
        
    logger.info("Replay finished.")
    
    # Save executed events
    output_file = "executed_ui_events.json"
    logger.info(f"Saving {len(executed_events)} executed events to {output_file}")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"executed_interactions": executed_events}, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save executed events: {e}")

    # Keep open for a moment to see result?
    time.sleep(2)
    ws.close()

if __name__ == "__main__":
    replay_interactions("cdp_captures/interaction/consolidated_interactions.json")
