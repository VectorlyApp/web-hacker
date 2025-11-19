#!/usr/bin/env python3
"""
Browser monitor script: Launch Chrome and record browser activity
"""

import os
import sys
import time
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Optional
import requests

# Colors for output (ANSI codes work on modern Windows 10+ terminals)
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

# Configuration
PORT = 9222
CDP_CAPTURES_DIR = Path("./cdp_captures")


def print_colored(text: str, color: str = NC) -> None:
    """Print colored text."""
    print(f"{color}{text}{NC}")


def check_chrome_running(port: int) -> bool:
    """Check if Chrome is already running in debug mode."""
    try:
        response = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=1)
        return response.status_code == 200
    except (requests.RequestException, requests.Timeout):
        return False


def find_chrome_path() -> Optional[str]:
    """Find Chrome executable path based on OS."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(chrome_path):
            return chrome_path
    elif system == "Linux":
        # Try common Linux Chrome/Chromium names
        for name in ["google-chrome", "chromium-browser", "chromium", "chrome"]:
            chrome_path = shutil.which(name)
            if chrome_path:
                return chrome_path
    elif system == "Windows":
        # Common Windows Chrome locations
        possible_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in possible_paths:
            if os.path.isfile(path):
                return path
        # Try to find in PATH
        chrome_path = shutil.which("chrome") or shutil.which("google-chrome")
        if chrome_path:
            return chrome_path
    
    return None


def launch_chrome(port: int) -> Optional[subprocess.Popen]:
    """Launch Chrome in debug mode."""
    chrome_path = find_chrome_path()
    
    if not chrome_path:
        print_colored("⚠️  Chrome not found automatically.", YELLOW)
        print("   Please launch Chrome manually with:")
        print(f"   --remote-debugging-port={port}")
        print()
        input("Press Enter when Chrome is running in debug mode...")
        return None
    
    # Create user data directory
    if platform.system() == "Windows":
        chrome_user_dir = os.path.expandvars(r"%USERPROFILE%\tmp\chrome")
    else:
        chrome_user_dir = os.path.expanduser("~/tmp/chrome")
    
    os.makedirs(chrome_user_dir, exist_ok=True)
    
    # Build Chrome arguments
    chrome_args = [
        chrome_path,
        f"--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={chrome_user_dir}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    
    # Launch Chrome
    print("🚀 Launching Chrome...")
    try:
        # On Windows, use CREATE_NEW_PROCESS_GROUP to detach
        creation_flags = 0
        if platform.system() == "Windows":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        
        process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        
        # Wait for Chrome to be ready
        print("⏳ Waiting for Chrome to start...")
        for _ in range(10):
            if check_chrome_running(port):
                print_colored("✅ Chrome is ready!", GREEN)
                # Give Chrome a moment to fully initialize tabs
                time.sleep(0.5)
                return process
            time.sleep(1)
        
        # Chrome didn't start in time
        print_colored("⚠️  Chrome failed to start automatically.", YELLOW)
        try:
            process.terminate()
            time.sleep(0.5)
            process.kill()
        except Exception:
            pass
        
        print("   Please launch Chrome manually with:")
        print(f"   --remote-debugging-port={port}")
        print()
        input("Press Enter when Chrome is running in debug mode...")
        return None
        
    except Exception as e:
        print_colored(f"⚠️  Error launching Chrome: {e}", YELLOW)
        print("   Please launch Chrome manually with:")
        print(f"   --remote-debugging-port={port}")
        print()
        input("Press Enter when Chrome is running in debug mode...")
        return None


def main():
    """Launch Chrome and start monitoring browser activity."""
    print_colored("🚀 Starting browser monitor...", GREEN)
    print()
    
    # Launch Chrome
    chrome_process = None
    if check_chrome_running(PORT):
        print_colored(f"✅ Chrome is already running in debug mode on port {PORT}", GREEN)
    else:
        chrome_process = launch_chrome(PORT)
    
    print()
    
    # Start monitoring
    print_colored("📹 Starting monitor (press Ctrl+C when done)...", GREEN)
    
    monitor_cmd = [
        "web-hacker-monitor",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--output-dir", str(CDP_CAPTURES_DIR),
        "--url", "about:blank",
    ]
    
    try:
        result = subprocess.run(monitor_cmd, check=True)
        if result.returncode == 0:
            print_colored(f"✅ Recording saved to {CDP_CAPTURES_DIR}", GREEN)
    except subprocess.CalledProcessError:
        print_colored("⚠️  Monitoring failed.", YELLOW)
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print_colored("✅ Recording stopped. Data saved to " + str(CDP_CAPTURES_DIR), GREEN)
        sys.exit(0)
    except FileNotFoundError:
        print_colored("⚠️  Command not found: web-hacker-monitor", YELLOW)
        print("   Make sure web-hacker is installed: pip install -e .")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_colored("⚠️  Interrupted by user.", YELLOW)
        sys.exit(0)
