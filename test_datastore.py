"""
Test script for LocalDiscoveryDataStore vectorstore creation and prompt generation.
"""

import os
from openai import OpenAI

from web_hacker.routine_discovery.data_store import LocalDiscoveryDataStore


def main():
    # Initialize OpenAI client
    client = OpenAI()

    # Hardcoded paths for testing
    cdp_captures_dir = "./cdp_captures"
    transactions_dir = os.path.join(cdp_captures_dir, "transactions")
    consolidated_transactions_path = os.path.join(cdp_captures_dir, "consolidated_transactions.json")
    storage_jsonl_path = os.path.join(cdp_captures_dir, "storage.jsonl")
    window_properties_path = os.path.join(cdp_captures_dir, "window_properties.json")
    tmp_dir = "./tmp_datastore_test"

    # Documentation and code directories
    documentation_dirs = ["./"]  # Current directory for .md files
    code_dirs = ["./web_hacker/data_models"]  # Data models code

    # Check if CDP captures exist
    cdp_exists = all([
        os.path.exists(transactions_dir),
        os.path.exists(consolidated_transactions_path),
        os.path.exists(storage_jsonl_path),
        os.path.exists(window_properties_path),
    ])

    if not cdp_exists:
        print("WARNING: CDP captures not found. Will only test documentation vectorstore.")
        print(f"  Expected: {cdp_captures_dir}")
        print()

    # Check documentation dirs
    print("Checking documentation directories:")
    for doc_dir in documentation_dirs:
        if os.path.exists(doc_dir):
            md_files = [f for f in os.listdir(doc_dir) if f.endswith(".md")]
            print(f"  {doc_dir}: {len(md_files)} .md files found")
        else:
            print(f"  {doc_dir}: NOT FOUND")

    # Check code dirs
    print("\nChecking code directories:")
    for code_dir in code_dirs:
        if os.path.exists(code_dir):
            py_files = []
            for root, _, files in os.walk(code_dir):
                py_files.extend([f for f in files if f.endswith(".py")])
            print(f"  {code_dir}: {len(py_files)} .py files found")
        else:
            print(f"  {code_dir}: NOT FOUND")

    print("\n" + "=" * 60)
    print("Creating LocalDiscoveryDataStore...")
    print("=" * 60)

    try:
        if cdp_exists:
            data_store = LocalDiscoveryDataStore(
                client=client,
                tmp_dir=tmp_dir,
                transactions_dir=transactions_dir,
                consolidated_transactions_path=consolidated_transactions_path,
                storage_jsonl_path=storage_jsonl_path,
                window_properties_path=window_properties_path,
                documentation_dirs=documentation_dirs,
                code_dirs=code_dirs,
            )
        else:
            # Create a minimal data store without CDP captures
            # We need to create dummy files for validation
            print("Creating dummy CDP captures for testing...")
            os.makedirs(transactions_dir, exist_ok=True)

            # Create minimal required files
            with open(consolidated_transactions_path, "w") as f:
                f.write("[]")
            with open(storage_jsonl_path, "w") as f:
                f.write("")
            with open(window_properties_path, "w") as f:
                f.write("{}")

            data_store = LocalDiscoveryDataStore(
                client=client,
                tmp_dir=tmp_dir,
                transactions_dir=transactions_dir,
                consolidated_transactions_path=consolidated_transactions_path,
                storage_jsonl_path=storage_jsonl_path,
                window_properties_path=window_properties_path,
                documentation_dirs=documentation_dirs,
                code_dirs=code_dirs,
            )

        print("DataStore created successfully!")

        # Test documentation vectorstore creation
        print("\n" + "=" * 60)
        print("Creating documentation vectorstore...")
        print("=" * 60)

        data_store.make_documentation_vectorstore()
        print(f"Documentation vectorstore ID: {data_store.documentation_vectorstore_id}")

        # Test CDP captures vectorstore creation
        print("\n" + "=" * 60)
        print("Creating CDP captures vectorstore...")
        print("=" * 60)

        data_store.make_cdp_captures_vectorstore()
        print(f"CDP captures vectorstore ID: {data_store.cdp_captures_vectorstore_id}")

        # Generate and print the prompt
        print("\n" + "=" * 60)
        print("Generated Data Store Prompt:")
        print("=" * 60)
        prompt = data_store.generate_data_store_prompt()
        print(prompt)

        # Clean up
        print("\n" + "=" * 60)
        print("Cleaning up vectorstores...")
        print("=" * 60)

        data_store.clean_up()
        print("Cleanup complete!")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up dummy files if we created them
        if not cdp_exists:
            import shutil
            if os.path.exists(cdp_captures_dir):
                shutil.rmtree(cdp_captures_dir)
                print("Removed dummy CDP captures directory")


if __name__ == "__main__":
    main()
