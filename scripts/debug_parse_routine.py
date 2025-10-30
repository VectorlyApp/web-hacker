#!/usr/bin/env python3
"""
Minimal script to debug llm_parse_text_to_model → Routine parsing.

Usage:
  OPENAI_API_KEY=... python scripts/debug_parse_routine.py
"""

import os
import json
from openai import OpenAI

from src.utils.llm_utils import llm_parse_text_to_model
from src.data_models.routine import Routine
from dotenv import load_dotenv

load_dotenv()




def main() -> None:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # Provide a tiny example text that should parse into Routine according to the schema
    example_text = {
        "name": "Search Trains",
        "description": "Navigate to site, fetch trains, return results",
        "parameters": [
            {
                "name": "origin",
                "required": True,
                "description": "Origin station code",
                "default": None,
                "examples": ["NYP"]
            },
            {
                "name": "destination",
                "required": True,
                "description": "Destination station code",
                "default": None,
                "examples": ["BOS"]
            }
        ],
        "operations": [
            {
                "type": "navigate",
                "url": "https://www.amtrak.com/"
            },
            {
                "type": "fetch",
                "endpoint": {
                    "url": "https://api.amtrak.com/search?from={{origin}}&to={{destination}}",
                    "description": "Search trains",
                    "method": "GET",
                    "headers": {},
                    "body": {},
                    "credentials": "same-origin"
                },
                "session_storage_key": "trains"
            },
            {
                "type": "return",
                "session_storage_key": "trains"
            }
        ]
    }

    text = json.dumps(example_text, ensure_ascii=False)
    context = "Debug parse Routine from example JSON"

    parsed = llm_parse_text_to_model(
        text=text,
        context=context,
        pydantic_model=Routine,
        client=client,
        llm_model=os.environ.get("LLM_PARSE_MODEL", "gpt-5-nano"),
        n_tries=3,
    )

    print("Parsed Routine (pydantic):")
    print(parsed)
    print("\nAs JSON:")
    print(parsed.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


