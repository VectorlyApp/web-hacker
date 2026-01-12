#!/usr/bin/env python3
"""
Script to run benchmark tests against generated routines.

This script loads a test config file, uses the ground truth routine as the
generated routine (for testing purposes), and runs all deterministic and LLM tests.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from openai import OpenAI

from web_hacker.data_models.benchmarks import DeterministicTest, LLMTest, LLMTestResult


def load_test_config(config_path: str) -> dict:
    """Load a test configuration file."""
    with open(config_path, "r") as f:
        return json.load(f)


def run_deterministic_tests(
    tests: list[dict],
    data: dict,
    verbose: bool = False
) -> tuple[int, int, list[dict]]:
    """
    Run deterministic tests against the data.

    Returns:
        tuple of (passed_count, total_count, results)
    """
    results = []
    passed = 0

    for test_data in tests:
        test = DeterministicTest.model_validate(test_data)
        result = test.expression.evaluate(data)

        results.append({
            "name": test.name,
            "description": test.description,
            "passed": result,
            "expression": test.expression.stringify()
        })

        if result:
            passed += 1
            if verbose:
                print(f"  ✓ {test.name}")
        else:
            if verbose:
                print(f"  ✗ {test.name}")
                print(f"    Expression: {test.expression.stringify()}")

    return passed, len(tests), results


def interpolate_prompt(prompt: str, data: dict) -> str:
    """
    Interpolate placeholders in the prompt with values from data.

    Supports:
    - {{key}} -> data["key"]
    - {{key.subkey}} -> data["key"]["subkey"]
    """
    def replace_placeholder(match: re.Match) -> str:
        path = match.group(1)
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return match.group(0)  # Return original if path not found
        return json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value)

    return re.sub(r"\{\{([^}]+)\}\}", replace_placeholder, prompt)


def run_llm_tests(
    tests: list[dict],
    data: dict,
    client: OpenAI,
    verbose: bool = False
) -> tuple[int, int, list[dict]]:
    """
    Run LLM tests against the data.

    Args:
        tests: List of LLM test configurations
        data: Data dict containing ground_truth_routine, generated_routine, task
        client: OpenAI client instance
        verbose: Whether to print detailed results

    Returns:
        tuple of (passed_count, total_count, results)
    """
    results = []
    passed = 0

    for test_data in tests:
        test = LLMTest.model_validate(test_data)

        # Interpolate placeholders in the prompt
        interpolated_prompt = interpolate_prompt(test.prompt, data)

        # Build the full prompt with scoring instructions
        full_prompt = (
            f"{interpolated_prompt}\n\n"
            f"Provide a score between {test.score_range[0]} and {test.score_range[1]}.\n"
            f"Respond with JSON in this exact format:\n"
            f'{{"score": <number>, "rationale": "<explanation>"}}'
        )

        # Run the LLM evaluation
        response = client.responses.parse(
            model=test.model,
            input=[{"role": "user", "content": full_prompt}],
            text_format=LLMTestResult
        )
        result = response.output_parsed

        # Check if passed
        test_passed = result.passed(test.passing_threshold)
        if test_passed:
            passed += 1

        results.append({
            "name": test.name,
            "description": test.description,
            "score": result.score,
            "rationale": result.rationale,
            "threshold": test.passing_threshold,
            "passed": test_passed
        })

        if verbose:
            status = "✓" if test_passed else "✗"
            print(f"  {status} {test.name}: {result.score:.2f} (threshold: {test.passing_threshold})")
            if result.rationale:
                print(f"    Rationale: {result.rationale[:100]}...")

    return passed, len(tests), results


def main():
    parser = argparse.ArgumentParser(
        description="Run benchmark tests against routines"
    )
    parser.add_argument(
        "config_path",
        help="Path to the test config JSON file"
    )
    parser.add_argument(
        "--generated-routine",
        help="Path to a generated routine JSON file (optional, defaults to using ground truth)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed test results"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--run-llm-tests",
        action="store_true",
        help="Run LLM-based tests (requires OpenAI API key)"
    )

    args = parser.parse_args()

    # Load the test config
    config = load_test_config(args.config_path)

    # Get the ground truth routine
    ground_truth = config.get("ground_truth_routine", {})

    # Get or create the generated routine
    if args.generated_routine:
        with open(args.generated_routine, "r") as f:
            generated = json.load(f)
    else:
        # Use ground truth as generated routine for testing
        generated = ground_truth.copy()

    # Build the data object that tests will evaluate against
    data = {
        "ground_truth_routine": ground_truth,
        "generated_routine": generated,
        "task": config.get("task", "")
    }

    # Run deterministic tests
    deterministic_tests = config.get("deterministic_tests", [])
    llm_tests = config.get("llm_tests", [])

    if not args.json:
        print(f"\nRunning benchmark: {config.get('name', 'Unknown')}")
        print(f"Description: {config.get('description', 'No description')}")
        print(f"\n{'='*60}")
        print("Deterministic Tests:")
        print(f"{'='*60}")

    det_passed, det_total, det_results = run_deterministic_tests(
        deterministic_tests,
        data,
        verbose=args.verbose or not args.json
    )

    # Run LLM tests if requested
    llm_passed, llm_total, llm_results = 0, 0, []
    if args.run_llm_tests and llm_tests:
        if not args.json:
            print(f"\n{'='*60}")
            print("LLM Tests:")
            print(f"{'='*60}")

        client = OpenAI()
        llm_passed, llm_total, llm_results = run_llm_tests(
            llm_tests,
            data,
            client,
            verbose=args.verbose or not args.json
        )

    if args.json:
        output = {
            "benchmark_name": config.get("name"),
            "description": config.get("description"),
            "deterministic_tests": {
                "passed": det_passed,
                "total": det_total,
                "pass_rate": det_passed / det_total if det_total > 0 else 0,
                "results": det_results
            }
        }
        if args.run_llm_tests:
            output["llm_tests"] = {
                "passed": llm_passed,
                "total": llm_total,
                "pass_rate": llm_passed / llm_total if llm_total > 0 else 0,
                "results": llm_results
            }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print("Summary:")
        print(f"{'='*60}")
        if det_total > 0:
            print(f"Deterministic: {det_passed}/{det_total} passed ({100*det_passed/det_total:.1f}%)")
        else:
            print("Deterministic: No tests to run")

        if args.run_llm_tests and llm_total > 0:
            print(f"LLM Tests: {llm_passed}/{llm_total} passed ({100*llm_passed/llm_total:.1f}%)")
        elif args.run_llm_tests:
            print("LLM Tests: No tests to run")

        total_passed = det_passed + llm_passed
        total_tests = det_total + llm_total
        if total_tests > 0:
            print(f"\nTotal: {total_passed}/{total_tests} passed ({100*total_passed/total_tests:.1f}%)")
        print(f"{'='*60}\n")

        # Exit with non-zero code if any tests failed
        if total_passed < total_tests:
            sys.exit(1)


if __name__ == "__main__":
    main()
