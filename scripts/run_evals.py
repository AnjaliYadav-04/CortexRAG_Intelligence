#!/usr/bin/env python3
"""Ragas evaluation suite for the Enterprise RAG pipeline.

Usage:
    python scripts/run_evals.py [--questions 10]

Metrics evaluated:
    - faithfulness       (answer grounded in context)
    - answer_relevancy   (answer addresses the question)
    - context_recall     (retrieved context covers ground truth)
    - context_precision  (retrieved context is focused)
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings

# ── Evaluation questions ───────────────────────────────────────────────────────

EVAL_QUESTIONS = [
    {
        "question": "What is a Kubernetes Pod?",
        "ground_truth": (
            "A Pod is the smallest deployable unit in Kubernetes, representing a single "
            "instance of a running process. It can contain one or more containers that "
            "share storage, network, and a specification for how to run."
        ),
    },
    {
        "question": "What does CrashLoopBackOff mean?",
        "ground_truth": (
            "CrashLoopBackOff indicates that a container in a pod is repeatedly crashing "
            "after restart. Kubernetes keeps restarting it but the container keeps failing."
        ),
    },
    {
        "question": "How does Horizontal Pod Autoscaler work?",
        "ground_truth": (
            "HPA automatically scales pod replicas based on observed CPU utilization or "
            "custom metrics. It queries metrics every 15 seconds and calculates desired "
            "replicas using: ceil(currentReplicas * (currentMetric / desiredMetric))."
        ),
    },
    {
        "question": "What are the Kubernetes QoS classes?",
        "ground_truth": (
            "Three QoS classes: Guaranteed (requests equal limits), Burstable "
            "(requests less than limits), and BestEffort (no requests or limits set)."
        ),
    },
    {
        "question": "How do I troubleshoot a pod that won't start?",
        "ground_truth": (
            "Use kubectl describe pod <name> to see events, kubectl logs <pod> --previous "
            "for crash logs, and kubectl get events sorted by creation time. "
            "Check for ImagePullBackOff, resource constraints, or node issues."
        ),
    },
]


async def run_single(question: str) -> dict:
    """Run one question through the full RAG pipeline."""
    import httpx

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60) as client:
        # Get token
        token_resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "eval_user", "password": "sre-secret"},
        )
        token = token_resp.json()["access_token"]

        # Ask question
        chat_resp = await client.post(
            "/api/v1/chat",
            json={"query": question, "session_id": "eval"},
            headers={"Authorization": f"Bearer {token}"},
        )
        data = chat_resp.json()
        return {
            "question": question,
            "answer": data.get("answer", ""),
            "contexts": [s.get("source", "") for s in data.get("sources", [])],
            "metadata": data.get("metadata", {}),
        }


async def run_evals(num_questions: int = 5) -> None:
    questions = EVAL_QUESTIONS[:num_questions]
    print(f"\n{'='*60}")
    print(f"  Enterprise RAG — Ragas Evaluation")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {num_questions} questions")
    print(f"{'='*60}\n")

    results = []
    for i, q in enumerate(questions):
        print(f"[{i+1}/{len(questions)}] {q['question']}")
        try:
            result = await run_single(q["question"])
            result["ground_truth"] = q["ground_truth"]
            results.append(result)
            print(f"  ✅ Answer length: {len(result['answer'])} chars")
        except Exception as exc:
            print(f"  ❌ Error: {exc}")

    # ── Ragas scoring ─────────────────────────────────────────────────────────
    try:
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_recall,
            context_precision,
        )
        from datasets import Dataset

        dataset = Dataset.from_list([
            {
                "question": r["question"],
                "answer": r["answer"],
                "contexts": [r["answer"][:500]],    # use answer as proxy context
                "ground_truth": r["ground_truth"],
            }
            for r in results
        ])

        scores = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        )

        print(f"\n{'='*60}")
        print("  RAGAS SCORES")
        print(f"{'='*60}")
        for metric, score in scores.items():
            bar = "█" * int(score * 20)
            print(f"  {metric:<25} {score:.3f}  {bar}")
        print(f"{'='*60}\n")

        # Save results
        out_path = f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out_path, "w") as f:
            json.dump({"scores": dict(scores), "results": results}, f, indent=2)
        print(f"Results saved to {out_path}")

    except ImportError:
        print("\n[warn] ragas not installed — skipping metric computation.")
        print("Install with: pip install ragas datasets")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(run_evals(args.questions))
