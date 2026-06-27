"""Prove — against the real Anthropic API — that web search actually works.

Run locally with your key (it is never committed):

    BLVCKSHELL_ANTHROPIC_API_KEY=sk-ant-... poetry run python -m scripts.verify_web_search

It does two independent checks:

  PART A — Raw API: calls Claude directly with the web_search tool and inspects
  the *raw* response blocks. This is the unambiguous proof: it reports whether
  the model actually executed a server-side search, how many, and the source
  domains it cited. Our LLMClient drops these non-text blocks (it only keeps the
  final text), so this is the only place the search itself is directly visible.

  PART B — Full brain path: runs the real Venture brain through the real agent
  loop and orchestrator (in-memory bus, real Claude), exactly as production
  does, and prints the briefing a user would see — so you can judge whether the
  integration produces grounded, cited output, not just whether the API works.

A deliberately verifiable prompt is used (current Teal/Huntr paid-tier pricing):
if the output names real, current dollar figures with sources, search worked; if
it hedges ("I don't have real-time data") or invents round numbers with no
source, it did not.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import NoReturn

PROMPT = (
    "What do Teal and Huntr currently charge for their paid subscription tiers? "
    "Give the exact current prices and name the source for each."
)


def _fail(msg: str) -> NoReturn:
    print(f"\n\033[91m✗ {msg}\033[0m")
    sys.exit(1)


async def part_a_raw_api(api_key: str, model: str) -> bool:
    """Call Claude directly with web_search and inspect the raw response blocks."""
    from anthropic import AsyncAnthropic

    print("\n=== PART A — raw Anthropic API (does search actually execute?) ===")
    client = AsyncAnthropic(api_key=api_key, max_retries=3)
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": PROMPT}],
        )
    except Exception as exc:
        print(f"\033[91mAPI call raised: {type(exc).__name__}: {exc}\033[0m")
        return False

    searches = 0
    sources: set[str] = set()
    text_parts: list[str] = []
    for block in resp.content:
        btype = getattr(block, "type", "")
        if btype == "server_tool_use" and getattr(block, "name", "") == "web_search":
            searches += 1
        elif btype == "web_search_tool_result":
            for item in getattr(block, "content", []) or []:
                url = getattr(item, "url", None)
                if url:
                    sources.add(url.split("/")[2] if "//" in url else url)
        elif btype == "text":
            text_parts.append(getattr(block, "text", ""))

    print(f"server-side searches executed : {searches}")
    print(f"distinct source domains cited : {len(sources)}")
    for s in sorted(sources):
        print(f"  - {s}")
    print(f"stop_reason                   : {resp.stop_reason}")
    print(f"input/output tokens           : {resp.usage.input_tokens}/{resp.usage.output_tokens}")
    print("\n--- model's answer ---")
    print("".join(text_parts).strip() or "(no text returned)")

    ok = searches > 0 and len(sources) > 0
    print(
        "\n\033[92m✓ PART A PASS — search executed and cited real sources\033[0m"
        if ok
        else "\033[91m✗ PART A FAIL — no server-side search / no sources in the response\033[0m"
    )
    return ok


async def part_b_brain_path(api_key: str, model: str) -> bool:
    """Run the real Venture brain through the real harness pipeline."""
    from harness.config import Settings
    from harness.core.harness import Harness

    print("\n\n=== PART B — full Venture brain path (what production runs) ===")
    settings = Settings(
        environment="verify",
        use_in_memory_bus=True,
        use_fake_llm=False,
        anthropic_api_key=api_key,
        anthropic_model=model,
        supabase_url=None,
        supabase_key=None,
        log_level="WARNING",
        worker_brain_modules="brains.examples.venture:VentureBrain",
    )
    harness = Harness(settings)
    await harness.startup()
    try:
        run = await harness.run_pipeline(PROMPT)
        print(f"pipeline status: {run.status.value}")
        for r in run.results:
            print(f"\n--- [{r.brain_id}] {r.status.value} ---")
            print((r.summary or r.error or "(no summary)").strip())
        print("\n--- synthesis ---")
        print((run.output or "(empty)").strip())
        # Heuristic: grounded answers carry $ figures and a source-y word.
        blob = " ".join([run.output or "", *[r.summary or "" for r in run.results]]).lower()
        grounded = "$" in blob and any(
            w in blob for w in ("teal", "huntr", "source", "according", "as of", "http")
        )
        ok = run.status.value in ("COMPLETED", "PARTIAL") and grounded
        pass_msg = "\n\033[92m✓ PART B PASS — brain produced grounded, priced output\033[0m"
        warn_msg = (
            "\n\033[93m⚠ PART B INCONCLUSIVE — read the output above and "
            "judge for yourself\033[0m"
        )
        print(pass_msg if ok else warn_msg)
        return ok
    finally:
        await harness.shutdown()


async def main() -> None:
    api_key = os.environ.get("BLVCKSHELL_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        _fail(
            "No API key. Set BLVCKSHELL_ANTHROPIC_API_KEY (your real key) and re-run.\n"
            "  This script makes real, billable Anthropic calls — it is the only way\n"
            "  to verify web search actually works; tests cannot (they use the fake LLM)."
        )
    model = os.environ.get("BLVCKSHELL_ANTHROPIC_MODEL", "claude-sonnet-4-6")
    print(f"Using model: {model}")

    a = await part_a_raw_api(api_key, model)
    b = await part_b_brain_path(api_key, model)

    print("\n" + "=" * 60)
    if a and b:
        print("\033[92mRESULT: web search is working end-to-end.\033[0m")
    elif a and not b:
        print(
            "\033[93mRESULT: search works at the API level, but the brain path "
            "didn't clearly surface it. Read PART B output above.\033[0m"
        )
    else:
        print("\033[91mRESULT: web search is NOT working. See PART A output above.\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
