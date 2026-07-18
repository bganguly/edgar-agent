"""
5 scripted simulation tests against the running EDGAR Agent backend.
Run: python tests/simulation_tests.py
Backend must be running at http://localhost:8000
"""

import json
import sys
import time
import httpx

BASE_URL = "http://localhost:8000"

SCENARIOS = [
    {
        "id": "1",
        "name": "Apple Revenue",
        "message": "What was Apple's total revenue in its most recent 10-K filing?",
        "must_contain_any": ["revenue", "net sales", "billion", "$"],
    },
    {
        "id": "2",
        "name": "Tesla Risk Factors",
        "message": "What are the main risk factors Tesla disclosed in its 10-K?",
        "must_contain_any": ["risk", "competition", "supply", "regulatory", "demand"],
    },
    {
        "id": "3",
        "name": "Microsoft Cloud Business",
        "message": "Describe Microsoft's cloud computing business segment from its 10-K.",
        "must_contain_any": ["azure", "cloud", "intelligent cloud", "revenue"],
    },
    {
        "id": "4",
        "name": "Amazon Employees",
        "message": "How many employees did Amazon report in its most recent 10-K filing?",
        "must_contain_any": ["employee", "full-time", "workforce", "approximately"],
    },
    {
        "id": "5",
        "name": "Nvidia GPU Business",
        "message": "What does Nvidia say about its data center and GPU business in its 10-K?",
        "must_contain_any": ["data center", "gpu", "accelerat", "compute"],
    },
]


def stream_chat(message: str, session_id: str | None = None) -> tuple[str, list[str], str]:
    """Returns (full_answer, tool_calls_used, session_id)."""
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    answer = ""
    tools_called = []
    returned_session_id = session_id or ""

    with httpx.Client(timeout=120) as client:
        with client.stream("POST", f"{BASE_URL}/chat", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if event["type"] == "token":
                    answer += event["text"]
                elif event["type"] == "tool_call":
                    tools_called.append(event["tool"])
                elif event["type"] == "session_id":
                    returned_session_id = event["session_id"]

    return answer, tools_called, returned_session_id


def run_scenario(scenario: dict) -> bool:
    print(f"\n{'='*60}")
    print(f"Scenario {scenario['id']}: {scenario['name']}")
    print(f"Q: {scenario['message']}")
    print("-" * 60)

    try:
        start = time.time()
        answer, tools, sid = stream_chat(scenario["message"])
        elapsed = time.time() - start

        print(f"Tools called: {tools}")
        print(f"Answer ({len(answer)} chars, {elapsed:.1f}s):")
        print(answer[:500] + ("..." if len(answer) > 500 else ""))

        answer_lower = answer.lower()
        passed = any(kw.lower() in answer_lower for kw in scenario["must_contain_any"])
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"\nStatus: {status}")
        if not passed:
            print(f"Expected any of: {scenario['must_contain_any']}")
        return passed

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    print("EDGAR Agent — Simulation Tests")
    print(f"Backend: {BASE_URL}")

    results = []
    for scenario in SCENARIOS:
        passed = run_scenario(scenario)
        results.append((scenario["name"], passed))

    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print("=" * 60)
    for name, passed in results:
        print(f"  {'✓' if passed else '✗'} {name}")

    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    print(f"\n{passed_count}/{total} scenarios passed")

    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
