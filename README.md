# social-listening-agent

A small, runnable example of a social listening agent: Claude runs an agentic loop over two tools that wrap the [xpoz](https://xpoz.ai) Python SDK, searches Twitter/X, Reddit, Instagram, and TikTok for a brand or topic and its competitors, reads the comments on the posts that matter, and writes a themed markdown report with quoted posts, a sentiment split, and suggested actions.

Built and open-sourced by the team at [xpoz.ai](https://xpoz.ai). The full walkthrough is on the xpoz blog: [Building a Social Listening AI Agent with Claude and xpoz MCP](https://www.xpoz.ai/blog/tutorials/build-a-social-listening-ai-agent-with-claude-and-xpoz-mcp/).

## What it does

```
python agent.py "espresso machines" --competitors Breville "De'Longhi" --days 14
```

1. Claude searches the topic on each platform for the date window, then runs a second pass with opinion words (broken, love, switched, vs) to surface reactions rather than announcements.
2. It searches each competitor so the report can compare share of conversation.
3. It pulls the comments on the two or three highest-engagement posts.
4. After at most `--search-budget` tool calls it writes `reports/<date>-<topic>.md` with six fixed sections: summary, sentiment split, top themes with quoted posts and links, competitor mentions, suggested actions, and method.

A real run on "espresso machines" is in [examples/espresso-machines.md](examples/espresso-machines.md).

## Quickstart

You need Python 3.10+, an Anthropic API key, and an xpoz key. The xpoz trial token needs no sign-up and lasts five days:

```bash
git clone https://github.com/XPOZpublic/social-listening-agent.git && cd social-listening-agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Put your `ANTHROPIC_API_KEY` in `.env`. For `XPOZ_API_KEY`, either use your key from [xpoz.ai/get-token](https://xpoz.ai/get-token) or request a trial token:

```bash
curl -X POST https://api.xpoz.ai/api/trial/token \
  -H "Content-Type: application/json" \
  -d '{"source": "cloned XPOZpublic/social-listening-agent from github", "useCase": "trying the social listening agent example on my brand"}'
```

The response carries `data.accessKey`, a token starting with `TRIAL`. Then run:

```bash
.venv/bin/python agent.py "your brand" --competitors "Competitor A" "Competitor B" --days 14 --limit 5
```

Trial tokens return at most five results per call and read cached data only, so keep `--limit 5` on a trial. A full key lifts the cap, adds pagination and CSV export, and returns live data.

## How it works

| File | What it holds |
|------|---------------|
| `agent.py` | The agentic loop: system prompt with the report contract, the Claude call with tools, tool dispatch, and writing the report |
| `tools.py` | Two tool definitions (`search_posts`, `get_comments`), the SDK calls behind them, and a normalizer that turns four platforms' post models into one shape |
| `examples/` | A real report produced with a trial token |

The loop is the plain Messages API pattern: call Claude with the tools, run every `tool_use` block Claude returns, send all results back in one user message, repeat until `stop_reason` is not `tool_use`. The final assistant text is the report. The model is `claude-sonnet-5`; change `MODEL` in `agent.py` to use another.

`search_posts` accepts exact phrases in double quotes and `AND`, `OR`, `NOT` operators, plus `start_date` and `end_date`. `get_comments` reads replies on Twitter/X, comments on Instagram and TikTok, and the comment tree on Reddit. Both return JSON rows with `platform`, `id`, `author`, `text`, engagement counts, `date`, and `url`.

## Cost

xpoz indexes billions of posts across the four platforms and charges per query, not per result. The trial token is free for five days. The Free tier is a one-time allowance of up to 75,000 results with no credit card; Pro is $20 a month for up to 1,000,000 results a month. A ten-call run like the example uses a small fraction of the Free tier. Claude Sonnet 5 tokens for that run cost a few cents.

## No code needed?

The same tools are available to Claude Desktop and Claude Code through the remote MCP server at `https://mcp.xpoz.ai/mcp` (sign in with Google on first use). Ask Claude for the same report in plain language and it will run the searches itself. Docs: [xpoz.ai/docs](https://xpoz.ai/docs).

## License

MIT
