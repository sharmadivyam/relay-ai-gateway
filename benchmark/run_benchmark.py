#!/usr/bin/env python3
"""
benchmark/run_benchmark.py — Smart Routing + Compression Savings Benchmark

Proves the cost savings from smart routing analytically:
  - Baseline:   every prompt always routed to gpt-4o (premium)
  - Optimized:  smart routing sends simple prompts to gpt-4o-mini

No gateway imports required. Runs standalone against prompts.json in the
same directory. Requires tiktoken (already installed via requirements.txt).

Usage:
    py -3 benchmark/run_benchmark.py
    py -3 benchmark/run_benchmark.py --prompts benchmark/prompts.json
"""
import argparse
import json
import os
import sys

try:
    import tiktoken
except ImportError:
    sys.exit("tiktoken is required: pip install tiktoken")

# ---------------------------------------------------------------------------
# Configuration — mirrors gateway's COST_PER_1K and routing rules exactly
# ---------------------------------------------------------------------------

BASELINE_MODEL  = "gpt-4o"       # premium: always used when flags are off
CHEAP_MODEL     = "gpt-4o-mini"  # cheap:   used for simple prompts when routing is on

COST_PER_1K = {
    "gpt-4o":      {"input": 0.005,   "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}

COMPLEX_KEYWORDS = ("explain", "analyze", "step by step", "summarize in detail")
ROUTING_TOKEN_THRESHOLD = 300
COMPLETION_ESTIMATE = 200  # assumed output tokens per request (conservative, fixed)


# ---------------------------------------------------------------------------
# Routing logic — mirrors smart_router.route() exactly, no import needed
# ---------------------------------------------------------------------------

def classify_prompt(text: str, token_count: int) -> str:
    """Returns 'simple' or 'complex' using the same rules as smart_router.route()."""
    has_code = "```" in text or "def " in text or "function " in text
    is_complex = (
        token_count > ROUTING_TOKEN_THRESHOLD
        or has_code
        or any(k in text.lower() for k in COMPLEX_KEYWORDS)
    )
    return "complex" if is_complex else "simple"


def count_tokens(text: str, enc) -> int:
    return len(enc.encode(text))


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_1K.get(model, {"input": 0.005, "output": 0.015})
    return (input_tokens / 1000 * rates["input"]) + (output_tokens / 1000 * rates["output"])


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(prompts_path: str) -> None:
    with open(prompts_path, encoding="utf-8") as f:
        prompts = json.load(f)

    enc = tiktoken.get_encoding("cl100k_base")

    results = []
    for p in prompts:
        text        = p["text"]
        pid         = p["id"]
        tokens      = count_tokens(text, enc)
        tier        = classify_prompt(text, tokens)
        routed_model = CHEAP_MODEL if tier == "simple" else BASELINE_MODEL

        baseline_cost  = compute_cost(BASELINE_MODEL, tokens, COMPLETION_ESTIMATE)
        optimized_cost = compute_cost(routed_model,   tokens, COMPLETION_ESTIMATE)
        saved          = baseline_cost - optimized_cost
        saved_pct      = (saved / baseline_cost * 100) if baseline_cost > 0 else 0.0

        results.append({
            "id":             pid,
            "text":           text,
            "tier":           tier,
            "tokens":         tokens,
            "model":          routed_model,
            "baseline_usd":   baseline_cost,
            "optimized_usd":  optimized_cost,
            "saved_usd":      saved,
            "saved_pct":      saved_pct,
        })

    # Totals
    total_tokens    = sum(r["tokens"]        for r in results)
    total_baseline  = sum(r["baseline_usd"]  for r in results)
    total_optimized = sum(r["optimized_usd"] for r in results)
    total_saved     = total_baseline - total_optimized
    total_saved_pct = (total_saved / total_baseline * 100) if total_baseline > 0 else 0.0
    n_simple        = sum(1 for r in results if r["tier"] == "simple")
    n_complex       = len(results) - n_simple

    # ---------------------------------------------------------------------------
    # Print table
    # ---------------------------------------------------------------------------
    col_text  = 44
    col_tier  =  8
    col_tok   =  6
    col_usd   = 12
    col_pct   =  8

    sep = "-" * (col_text + col_tier + col_tok + col_usd * 3 + col_pct + 7)

    header = (
        f"{'Prompt':<{col_text}} "
        f"{'Tier':<{col_tier}} "
        f"{'Tokens':>{col_tok}} "
        f"{'Baseline($)':>{col_usd}} "
        f"{'Optimized($)':>{col_usd}} "
        f"{'Saved($)':>{col_usd}} "
        f"{'Saved(%)':>{col_pct}}"
    )

    print()
    print("=" * len(sep))
    print("  AI Gateway - Smart Routing Cost Benchmark")
    print(f"  Baseline model : {BASELINE_MODEL} (always premium, no routing)")
    print(f"  Routing logic  : simple -> {CHEAP_MODEL}  |  complex -> {BASELINE_MODEL}")
    print(f"  Prompts        : {len(results)}  ({n_simple} simple / {n_complex} complex)")
    print(f"  Completion est.: {COMPLETION_ESTIMATE} tokens per request")
    print("=" * len(sep))
    print()
    print(header)
    print(sep)

    for r in results:
        label = r["text"].replace("\n", " ")
        if len(label) > col_text - 1:
            label = label[:col_text - 4] + "..."
        print(
            f"{label:<{col_text}} "
            f"{r['tier']:<{col_tier}} "
            f"{r['tokens']:>{col_tok}} "
            f"{r['baseline_usd']:>{col_usd}.6f} "
            f"{r['optimized_usd']:>{col_usd}.6f} "
            f"{r['saved_usd']:>{col_usd}.6f} "
            f"{r['saved_pct']:>{col_pct-1}.1f}%"
        )

    print(sep)
    print(
        f"{'TOTAL (' + str(len(results)) + ' prompts)':<{col_text}} "
        f"{'':>{col_tier}} "
        f"{total_tokens:>{col_tok}} "
        f"{total_baseline:>{col_usd}.6f} "
        f"{total_optimized:>{col_usd}.6f} "
        f"{total_saved:>{col_usd}.6f} "
        f"{total_saved_pct:>{col_pct-1}.1f}%"
    )
    print()

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print("SUMMARY")
    print(f"  Total prompts    : {len(results)}")
    print(f"  Simple / Complex : {n_simple} / {n_complex}")
    print(f"  Total tokens     : {total_tokens:,}")
    print(f"  Baseline cost    : ${total_baseline:.6f}")
    print(f"  Optimized cost   : ${total_optimized:.6f}")
    print(f"  Total saved      : ${total_saved:.6f}")
    print(f"  Savings          : {total_saved_pct:.1f}%")
    print()

    # Write machine-readable results for README / CI
    out_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(out_dir, "results.md")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("# Benchmark Results\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        f.write(f"| Prompts | {len(results)} ({n_simple} simple / {n_complex} complex) |\n")
        f.write(f"| Total tokens | {total_tokens:,} |\n")
        f.write(f"| Baseline cost (all gpt-4o) | ${total_baseline:.6f} |\n")
        f.write(f"| Optimized cost (smart routing) | ${total_optimized:.6f} |\n")
        f.write(f"| Total saved | ${total_saved:.6f} |\n")
        f.write(f"| Savings % | {total_saved_pct:.1f}% |\n\n")
        f.write("## Per-prompt breakdown\n\n")
        f.write("| ID | Tier | Tokens | Baseline($) | Optimized($) | Saved($) | Saved(%) |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            label = r["text"].replace("\n", " ")[:60]
            f.write(
                f"| {r['id']} | {r['tier']} | {r['tokens']} "
                f"| {r['baseline_usd']:.6f} | {r['optimized_usd']:.6f} "
                f"| {r['saved_usd']:.6f} | {r['saved_pct']:.1f}% |\n"
            )

    print(f"Results written to: {results_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Gateway smart-routing cost benchmark")
    parser.add_argument(
        "--prompts",
        default=os.path.join(os.path.dirname(__file__), "prompts.json"),
        help="Path to prompts JSON file (default: benchmark/prompts.json)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.prompts):
        sys.exit(f"Prompts file not found: {args.prompts}")

    run_benchmark(args.prompts)
