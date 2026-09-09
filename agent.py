import argparse
import datetime
import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from xpoz import XpozClient, XpozError

from tools import TOOL_DEFINITIONS, run_tool

MODEL = "claude-sonnet-5"
MAX_TOKENS = 16000
MAX_TURNS = 24
REPORTS_DIR = Path("reports")

SYSTEM_PROMPT = """You are a social listening analyst. You have two tools over a social data index covering Twitter/X, Reddit, Instagram, and TikTok.

Work in this order:
1. Search the brand or topic on every platform for the requested window. Use exact phrases for multi-word names. Run one or two more searches with complaint, praise, or comparison words (for example "broken", "love", "vs", "switched") to surface opinions, not just announcements.
2. Search each competitor at least once so the report can compare share of conversation.
3. Read the comments on the two or three highest-engagement posts to capture how people reacted.
4. Stop searching after {search_budget} tool calls at most, then write the report.

Then write the final answer as a markdown report with exactly these sections:
# Social listening report: {topic}
## Summary (3-5 sentences: volume, overall sentiment, the one thing to act on)
## Sentiment split (a table: platform, positive, neutral, negative, sample size)
## Top themes (3-6 themes; each with a one-line description, one or two quoted example posts with their url, and which platform they came from)
## Competitor mentions (a table: name, posts found, dominant sentiment, one representative example)
## Suggested actions (3-5 concrete actions, each tied to a theme or post above)
## Method (which searches ran, the date window, sample sizes, and the caveat that counts are samples, not totals)

Classify sentiment from the post text itself. Quote posts verbatim and keep every url exactly as returned. Do not invent posts, numbers, or urls. If a search returns nothing, say so in Method. Write plain prose without em dashes."""


def build_prompt(topic: str, competitors: list[str], days: int) -> str:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    competitor_line = ", ".join(competitors) if competitors else "none given"
    return (
        f"Topic or brand: {topic}\n"
        f"Competitors: {competitor_line}\n"
        f"Date window: {start.isoformat()} to {end.isoformat()}\n"
        "Gather the mentions and write the report."
    )


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def run(topic: str, competitors: list[str], days: int, search_budget: int, per_search_limit: int) -> Path:
    claude = anthropic.Anthropic()
    xpoz = XpozClient(os.environ["XPOZ_API_KEY"])
    system = SYSTEM_PROMPT.format(search_budget=search_budget, topic=topic)
    messages = [{"role": "user", "content": build_prompt(topic, competitors, days)}]
    report_text = ""
    tool_calls = 0
    for _ in range(MAX_TURNS):
        response = claude.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            report_text = "".join(block.text for block in response.content if block.type == "text")
            break
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            arguments = dict(block.input)
            arguments["limit"] = min(int(arguments.get("limit") or per_search_limit), per_search_limit)
            tool_calls += 1
            print(f"[{tool_calls}] {block.name} {json.dumps(arguments)}")
            try:
                content = run_tool(xpoz, block.name, arguments)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
            except XpozError as error:
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(error), "is_error": True})
        messages.append({"role": "user", "content": results})
    xpoz.close()
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{datetime.date.today().isoformat()}-{slugify(topic)}.md"
    path.write_text(report_text, encoding="utf-8")
    print(f"report written to {path} after {tool_calls} tool calls")
    return path


def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Social listening agent: Claude plus the xpoz social data SDK")
    parser.add_argument("topic", help="brand or topic to listen for")
    parser.add_argument("--competitors", nargs="*", default=[], help="competitor names to compare against")
    parser.add_argument("--days", type=int, default=14, help="how many days back to search")
    parser.add_argument("--search-budget", type=int, default=12, help="maximum tool calls before the report is written")
    parser.add_argument("--limit", type=int, default=20, help="maximum posts per search (trial tokens return at most 5)")
    args = parser.parse_args()
    run(args.topic, args.competitors, args.days, args.search_budget, args.limit)


if __name__ == "__main__":
    main()
