#!/usr/bin/env python3
"""
Test script to PROVE response_id branching behavior in OpenAI Responses API.

Count to 8, then jump back 3 times to different points.
"""

import os
from openai import OpenAI


def main() -> None:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 60)
    print("PROVING response_id Branching - Count to 8, Jump 3 Times")
    print("=" * 60)

    # Store all response IDs
    responses: dict[int, tuple[str, str]] = {}  # num -> (response_id, output)

    # Step 1: Start at 1
    print("\n[Building the chain: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8]")
    print("-" * 60)

    resp = client.responses.create(
        model="gpt-5.1",
        input="You are a counting assistant. Your ONLY job is to say numbers. Start by saying: 1",
    )
    responses[1] = (resp.id, resp.output_text.strip())
    print(f"  1: {resp.output_text.strip():<10} (id saved)")
    prev_id = resp.id

    # Count 2 through 8
    for num in range(2, 9):
        resp = client.responses.create(
            model="gpt-5.1",
            input=f"Say the next number after {num-1}. ONLY output the number, nothing else.",
            previous_response_id=prev_id,
        )
        responses[num] = (resp.id, resp.output_text.strip())
        print(f"  {num}: {resp.output_text.strip():<10} (id saved)")
        prev_id = resp.id

    # Now do 3 jump tests
    print("\n" + "=" * 60)
    print("🔥 JUMP TEST 1: Back to position 2, ask for next")
    print("=" * 60)
    print(f"  Chain was: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8")
    print(f"  Jumping to id_2 (after '2' was said)")
    print(f"  Expected: 3")

    jump1 = client.responses.create(
        model="gpt-5.1",
        input="What comes after 2? Say ONLY the number.",
        previous_response_id=responses[2][0],
    )
    print(f"  🎯 RESULT: {jump1.output_text.strip()}")

    print("\n" + "=" * 60)
    print("🔥 JUMP TEST 2: Back to position 5, ask for next")
    print("=" * 60)
    print(f"  Jumping to id_5 (after '5' was said)")
    print(f"  Expected: 6")

    jump2 = client.responses.create(
        model="gpt-5.1",
        input="What comes after 5? Say ONLY the number.",
        previous_response_id=responses[5][0],
    )
    print(f"  🎯 RESULT: {jump2.output_text.strip()}")

    print("\n" + "=" * 60)
    print("🔥 JUMP TEST 3: Back to position 3, ask what was the last number")
    print("=" * 60)
    print(f"  Jumping to id_3 (after '3' was said)")
    print(f"  Expected: 3 (it should remember it just said 3)")

    jump3 = client.responses.create(
        model="gpt-5.1",
        input="What was the last number you said? Say ONLY that number.",
        previous_response_id=responses[3][0],
    )
    print(f"  🎯 RESULT: {jump3.output_text.strip()}")

    # Continue main chain to prove it's unaffected
    print("\n" + "=" * 60)
    print("🔄 MAIN CHAIN: Continue from 8")
    print("=" * 60)
    print(f"  Continuing from id_8")
    print(f"  Expected: 9")

    main_continue = client.responses.create(
        model="gpt-5.1",
        input="What comes next? Say ONLY the number.",
        previous_response_id=responses[8][0],
    )
    print(f"  🎯 RESULT: {main_continue.output_text.strip()}")

    # Final summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
    Main chain: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

    Branches created:
      • From id_2: jumped back, got → {}
      • From id_5: jumped back, got → {}
      • From id_3: jumped back, got → {}

    If all jumps returned expected values, branching is CONFIRMED.
    """.format(
        jump1.output_text.strip(),
        jump2.output_text.strip(),
        jump3.output_text.strip(),
    ))


if __name__ == "__main__":
    main()
