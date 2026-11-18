# Market data layout

One folder per market: `data/<market>/`. `chips` is the reference; every other market follows it.

| File | What it holds | Written by |
| --- | --- | --- |
| `companies.csv` | the companies of the chain plus a control group of unrelated large companies in the same countries | research |
| `edges.csv` | supplier -> customer links, each with its source, confidence and whether the customer critically depends on the supplier | research |
| `events.csv` | dated shocks (disasters, bans, fires, rulings) with a UTC timestamp and the companies hit | research |
| `stages.json` | per stage: Hebrew title, one-line rhythm, explanation, facts, how ordering works, weak points; plus sources, time constants and a reporting calendar | research |
| `market.json` | market name, definition, plain-language sentence per stage, key numbers, product lifecycle, history, open changes (regulation / technology / business moves) | research |
| `profiles.json`, `prices_weekly.json`, `news.json`, `earnings.json`, `pulses.json` | fetched automatically from free sources | scripts |

Rules for researched content
- Every claim carries a source key that exists in `sources`. A claim seen only in a search snippet is marked unverified.
- Numbers come from the source, never from memory.
- Hebrew text is plain and short: no jargon, no metaphors, one idea per sentence.
- `companies.csv` ids are short upper-case names; `ticker` is the Yahoo Finance symbol on the home exchange.
