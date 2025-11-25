#!/usr/bin/env python3
"""
Test script for productionize_routine function.
Loads a dev routine from JSON and converts it to a production routine.
"""

import json
import sys
from pathlib import Path

from openai import OpenAI

from web_hacker.config import Config
from web_hacker.data_models.dev_routine import Routine
from web_hacker.data_models.production_routine import Routine as ProductionRoutine
from web_hacker.utils.llm_utils import collect_text_from_response, manual_llm_parse_text_to_model


def productionize_routine(routine: Routine, client: OpenAI, llm_model: str = "gpt-5-mini") -> ProductionRoutine:
    """
    Productionize the routine into a production routine.
    Args:
        routine (Routine): The routine to productionize.
        client (OpenAI): The OpenAI client.
        llm_model (str): The LLM model to use.
    Returns:
        ProductionRoutine: The productionized routine.
    """
    message = (
        f"Please productionize the routine (from previosu step): {routine.model_dump_json()}"
        f"You need to clean up this routine to follow the following format: {ProductionRoutine.model_json_schema()}"
        f"Please respond in the following format: {ProductionRoutine.model_json_schema()}"
        f"You immediate output needs to be a valid JSON object that conforms to the production routine schema."
        f"CRITICAL: PLACEHOLDERS ARE REPLACED AT RUNTIME AND MUST RESULT IN VALID JSON! "
        f"EXPLANATION: Placeholders like {{{{key}}}} are replaced at runtime with actual values. The format you choose determines the resulting JSON type. "
        f"For STRING values: Use \\\"{{{{key}}}}\\\" format (escaped quote + placeholder + escaped quote). "
        f"This means in the JSON file you write: \"\\\"{{{{user_name}}}}\\\"\". At runtime, the \\\"{{{{user_name}}}}\\\" part gets replaced, "
        f"so \"\\\"{{{{user_name}}}}\\\"\" becomes \"John\" (valid JSON string). "
        f"For NUMERIC/NULL values: Use \"{{{{key}}}}\" format (regular quote + placeholder + quote). "
        f"This means in the JSON file you write: \"{{{{item_id}}}}\". At runtime, the {{{{item_id}}}} part gets replaced with the number, "
        f"and the surrounding quotes are removed, so \"{{{{item_id}}}}\" with value 42 becomes just 42 (valid JSON number, not string). "
        f"Example: \"{{{{total_price}}}}\" with value 29.99 → becomes 29.99 (quotes removed, valid JSON number). "
        f"Example: \"{{{{optional_data}}}}\" with null → becomes null (quotes removed, valid JSON null). "
        f"The resulting JSON MUST be valid and parseable after all placeholder replacements are done."
    )

    # call to the LLM API for productionization of the routine
    response = client.responses.create(
        model=llm_model,
        input=[{"role": "user", "content": message}],
    )
    
    # collect the text from the response
    response_text = collect_text_from_response(response)
    
    # parse the response to the pydantic model
    # context includes the user prompt + assistant response to help with parsing
    production_routine = manual_llm_parse_text_to_model(
        text=response_text,
        context=f"user: {message}\nassistant: {response_text}",
        pydantic_model=ProductionRoutine,
        client=client,
        llm_model=llm_model
    )
    
    return production_routine


def main():
    # Hardcoded path to routine.json
    input_path = Path("routine_discovery_output/routine.json")
    
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    # Load the dev routine from JSON
    print(f"Loading dev routine from: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        routine_data = json.load(f)
    
    # Convert to Routine object (dev routine)
    # Dev routines have 'headers' and 'body' as strings (JSON strings), not objects
    # Check if this is already a production routine (headers/body are dicts)
    if routine_data.get("operations"):
        first_fetch = next(
            (op for op in routine_data["operations"] if op.get("type") == "fetch"),
            None
        )
        if first_fetch and first_fetch.get("endpoint"):
            endpoint = first_fetch["endpoint"]
            if isinstance(endpoint.get("headers"), dict) and isinstance(endpoint.get("body"), dict):
                print("Error: This appears to be a production routine (headers/body are objects).")
                print("productionize_routine expects a dev routine (headers/body are JSON strings).")
                print("Please provide a dev routine JSON file.")
                sys.exit(1)
    
    try:
        routine = Routine(**routine_data)
    except Exception as e:
        print(f"Error: Failed to parse routine as dev routine: {e}")
        print("\nDev routine format requirements:")
        print("- 'headers' and 'body' in endpoints must be JSON strings (not objects)")
        print("- Example: 'headers': '{\"Content-Type\": \"application/json\"}'")
        print("- Example: 'body': '{\"key\": \"value\"}'")
        sys.exit(1)
    
    # Initialize OpenAI client
    if Config.OPENAI_API_KEY is None:
        print("Error: OPENAI_API_KEY not set in environment")
        sys.exit(1)
    
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    
    # Call productionize_routine
    print("Calling productionize_routine...")
    production_routine = productionize_routine(routine, client)
    
    # Save the production routine
    output_file = Path("routine_discovery_output/productionized_routine.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(production_routine.model_dump(), f, ensure_ascii=False, indent=2)
    
    print(f"Production routine saved to: {output_file}")
    print(f"Routine name: {production_routine.name}")
    print(f"Parameters: {len(production_routine.parameters)}")


if __name__ == "__main__":
    main()
