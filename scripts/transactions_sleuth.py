#!/usr/bin/env python3
"""
Transactions Sleuth: Analyze captured network transactions to answer user questions.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

# Ensure we can import web_hacker
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from web_hacker.config import Config

# Configure logging
logging.basicConfig(level=Config.LOG_LEVEL, format=Config.LOG_FORMAT)
logger = logging.getLogger(__name__)

def print_colored(text: str, color_code: str) -> None:
    """Print text in color."""
    print(f"{color_code}{text}\033[0m")

GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'

def check_captures_exist(base_dir: Path) -> bool:
    """Check if the captures directory exists."""
    if not base_dir.exists():
        print_colored(f"❌ Error: Captures directory not found at {base_dir}", RED)
        return False
    return True

def get_relevant_transactions(transactions_dir: Path, query: str) -> list[dict[str, Any]]:
    """
    Scan transaction directories and return relevant content.
    We'll focus on JSON responses and non-static assets.
    """
    relevant_data = []
    
    if not transactions_dir.exists():
        return []

    # Heuristics to skip static assets
    SKIP_EXTENSIONS = {'.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ico'}
    SKIP_SUBSTRINGS = {'assets', 'static', 'node_modules', 'vite', 'analytics', 'sentry', 'posthog'}

    print_colored("🔍 Scanning transactions...", BLUE)
    
    count = 0
    # Sort by time (directory name usually starts with timestamp)
    # But directory names are like "20251119_1763584454262_apply.ycombinator.com_graphql"
    # We can sort them to get the sequence of events.
    
    try:
        transaction_dirs = sorted(list(transactions_dir.iterdir()), key=lambda x: x.name)
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        return []

    for trans_dir in transaction_dirs:
        if not trans_dir.is_dir():
            continue
            
        dir_name = trans_dir.name.lower()
        
        # Simple filter: if it looks like a static asset or tracking, skip it
        # unless the query specifically asks for it.
        if any(s in dir_name for s in SKIP_SUBSTRINGS):
            continue
            
        # Check for response body
        body_file = None
        content_type = "unknown"
        
        # Priority: json > txt > html
        if (trans_dir / "response_body.json").exists():
            body_file = trans_dir / "response_body.json"
            content_type = "json"
        elif (trans_dir / "response_body.txt").exists():
            body_file = trans_dir / "response_body.txt"
            content_type = "text"
        elif (trans_dir / "response_body.html").exists():
            # HTML might be too big, but let's include it if it's not too huge
            body_file = trans_dir / "response_body.html"
            content_type = "html"
            
        if not body_file:
            continue
            
        # Read content
        try:
            with open(body_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            # Skip if content is huge (e.g. > 100KB) unless we are desperate
            if len(content) > 100_000:
                content = content[:100_000] + "... [TRUNCATED]"
            
            # Attempt to parse JSON to compact it
            if content_type == "json":
                try:
                    json_obj = json.loads(content)
                    content = json.dumps(json_obj) # Minify
                except:
                    pass
            
            relevant_data.append({
                "id": trans_dir.name,
                "type": content_type,
                "content": content
            })
            count += 1
            
        except Exception as e:
            logger.warning(f"Failed to read {body_file}: {e}")

    print_colored(f"✅ Found {count} potentially relevant transactions.", GREEN)
    return relevant_data

def query_llm(query: str, context_data: list[dict[str, Any]]) -> str:
    """Send query and context to LLM."""
    
    if not Config.OPENAI_API_KEY:
        return "❌ Error: OPENAI_API_KEY not found in environment variables."
        
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    
    # Construct context string
    # If context is too large, we might need to truncate or summarize.
    # For now, let's just dump it and hope it fits in the large context window of modern models.
    
    context_str = ""
    for item in context_data:
        context_str += f"\n--- Transaction: {item['id']} ---\n"
        context_str += f"Content: {item['content']}\n"
        
    system_prompt = (
        "You are a digital forensics expert ('Transactions Sleuth'). "
        "You analyze captured network traffic to answer user questions. "
        "The user will ask about specific details (like Zoom URLs, names, dates, etc.). "
        "Look through the provided JSON/Text transaction bodies carefully. "
        "If you find the answer, quote the specific value and the transaction ID where you found it. "
        "If the answer is not explicitly in the text, say so."
    )
    
    print_colored("Analyzing...", BLUE)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Or gpt-5 if available/configured
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Query: {query}\n\nCaptured Data:\n{context_str}"}
            ],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ LLM Error: {e}"

def main():
    print_colored("\n🕵️  Transactions Sleuth 🕵️", BLUE)
    print_colored("===========================", BLUE)
    
    cdp_dir = Path("./cdp_captures")
    if not check_captures_exist(cdp_dir):
        return

    transactions_dir = cdp_dir / "network" / "transactions"
    if not transactions_dir.exists():
        print_colored(f"❌ No transactions found in {transactions_dir}", RED)
        return

    # Get user query
    print()
    print("What are you looking for?")
    # eg: 'I have a YC W26 interview tomorrow and want to know as much as possible about it.
    
    try:
        query = input(f"{GREEN}Query: {'\033[0m'}")
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    if not query.strip():
        print("Empty query. Exiting.")
        return

    # Get data
    data = get_relevant_transactions(transactions_dir, query)
    
    if not data:
        print_colored("No relevant data found in captures.", YELLOW)
        return

    # Ask LLM
    answer = query_llm(query, data)
    
    print("\n" + "="*30 + "\n")
    print(answer)
    print("\n" + "="*30 + "\n")

if __name__ == "__main__":
    main()

