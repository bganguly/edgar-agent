"""
LLM-as-judge evaluation for EDGAR Agent.
Scores each conversation 1–5 on relevance and accuracy.

Run: python tests/eval.py
Backend must be running at http://localhost:8000
"""

import json
import sys
import time
import httpx
import anthropic

BASE_URL = "http://localhost:8000"

EVAL_CASES = [
    {
        "question": "What was Apple's total net sales in fiscal year 2023?",
        "expected_themes": "Apple total net sales revenue 2023 annual report 10-K dollar amount billions",
    },
    {
        "question": "What risks does Tesla mention regarding lithium and battery supply?",
        "expected_themes": "Tesla battery lithium supply chain risk factors 10-K shortage dependency",
    },
    {
        "question": "How does Microsoft describe its Azure cloud segment?",
        "expected_themes": "Microsoft Azure cloud intelligent cloud segment revenue growth 10-K",
    },
    {
        "question": "What is Amazon's stated business strategy in its 10-K?",
        "expected_themes": "Amazon long-term customer focus low prices selection convenience 10-K strategy",
    },
    {
        "question": "What does Nvidia say about AI and its data center revenue?",
        "expected_themes": "Nvidia data center AI revenue growth GPU accelerated computing 10-K",
    },
]

JUDGE_PROMPT = """You are an objective evaluator of AI assistant responses about SEC 10-K filings.

Question asked: {question}
Expected themes: {expected_themes}

Assistant's response:
---
{response}
---

Score the response on two dimensions, each 1–5:

RELEVANCE (1–5): Does the response address the question and mention relevant financial or business information?
1 = completely off-topic or empty
3 = partially relevant, missing key aspects
5 = highly relevant, directly addresses the question

ACCURACY (1–5): Does the response appear factually grounded (e.g., cites specific numbers, filing periods, realistic figures)?
1 = vague, no specifics, or clearly wrong
3 = some specifics but incomplete or uncertain
5 = specific, credible, well-sourced from filing text

Reply ONLY with valid JSON in this exact format:
{{"relevance": <1-5>, "accuracy": <1-5>, "rationale": "<one sentence>"}}"""


def stream_chat(message: str) -> str:
    answer = ""
    with httpx.Client(timeout=120) as client:
        with client.stream("POST", f"{BASE_URL}/chat", json={"message": message}) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                    if event["type"] == "token":
                        answer += event["text"]
                except json.JSONDecodeError:
                    continue
    return answer


def judge_response(question: str, expected_themes: str, response: str) -> dict:
    client = anthropic.Anthropic()
    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_themes=expected_themes,
        response=response[:3000],
    )
    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    return json.loads(raw)


def run_eval():
    print("EDGAR Agent — LLM-as-Judge Evaluation")
    print(f"Backend: {BASE_URL}")
    print("=" * 60)

    scores = []
    for i, case in enumerate(EVAL_CASES, 1):
        print(f"\nCase {i}: {case['question'][:60]}...")
        try:
            start = time.time()
            response = stream_chat(case["question"])
            elapsed = time.time() - start
            print(f"  Response ({len(response)} chars, {elapsed:.1f}s)")

            judgment = judge_response(case["question"], case["expected_themes"], response)
            rel = judgment["relevance"]
            acc = judgment["accuracy"]
            scores.append({"case": i, "relevance": rel, "accuracy": acc, "rationale": judgment.get("rationale", "")})
            print(f"  Relevance: {rel}/5  Accuracy: {acc}/5")
            print(f"  Judge: {judgment.get('rationale', '')}")
        except Exception as e:
            print(f"  ERROR: {e}")
            scores.append({"case": i, "relevance": 0, "accuracy": 0, "rationale": str(e)})

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print("=" * 60)

    valid = [s for s in scores if s["relevance"] > 0]
    if valid:
        avg_rel = sum(s["relevance"] for s in valid) / len(valid)
        avg_acc = sum(s["accuracy"] for s in valid) / len(valid)
        print(f"  Cases evaluated: {len(valid)}/{len(scores)}")
        print(f"  Avg Relevance:   {avg_rel:.2f}/5.0")
        print(f"  Avg Accuracy:    {avg_acc:.2f}/5.0")
        print(f"  Overall Score:   {(avg_rel + avg_acc) / 2:.2f}/5.0")
    else:
        print("  No valid scores collected.")

    print()
    for s in scores:
        status = f"R:{s['relevance']}/5 A:{s['accuracy']}/5"
        print(f"  Case {s['case']}: {status} — {s['rationale'][:80]}")

    overall = (avg_rel + avg_acc) / 2 if valid else 0
    sys.exit(0 if overall >= 3.0 else 1)


if __name__ == "__main__":
    run_eval()
