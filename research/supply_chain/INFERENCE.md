# "What is likely next": how the automatic system works

## The one rule
Numbers come from code, wording from a writer, and the verdict from the ledger.
No step is allowed to do another step's job.

| Step | File | What it does | What it may not do |
|---|---|---|---|
| History | `inference.py base` | Applies each rule to the past and counts how it ended (base rates, all markets pooled) | Be tuned per company |
| Detect | `inference.py detect` | Finds companies in that state today, by fixed thresholds | Use judgment |
| Gate | `_informative` | Publishes only with >= 30 past cases and >= 10 points gap from the plain average; the rest is counted as "checked, nothing to say" | Publish a hunch |
| Claim | `ledger/<market>/claims.jsonl` | One dated, testable sentence per card, hash-chained, one open claim per card | Be edited or restated |
| Write | `writer.py` | Template Hebrew; Claude rephrases when credentials exist | Add a number: text with a number not in the card is discarded |
| Score | `inference.py score` | When the date passes, compares the claim with what happened | Run after new claims (it runs before) |
| Show | page tab "מה הלאה" | Track record first, then at most: one market card, dated changes, 3 per rule | Hide the misses |

## Rules today
- `growth`: revenue up 25%+ on the year -> growth a year later is lower (history: 81% to 93% of cases, US chip filers).
- `market_growth`: many companies in that state at once -> one market card instead of thirty.
- `vol`: stock in the jumpiest third of its market -> stays there next half-year (72% vs 33% by chance).
- `price_run_up` / `price_drop`: checked, history does not lean either way, so nothing is shown.
- `date`: a dated change within 100 days. Not a forecast; a date and who stands next to it.

## Adding a rule
1. A `base_*` function: the rule applied to history, with a plain average to compare against.
2. A `detect_*` function returning cards with `see`, `past`, `claim` (metric, operator, value, weeks).
3. A branch in `_outcome` (how the claim is measured) and in `writer.template`.
If the base rate does not pass the gate, the rule stays silent by itself.

## Running
    python -m research.supply_chain.auto              # everything, every market
    python -m research.supply_chain.auto --no-fetch   # from data on disk
`.github/workflows/daily.yml` runs it on weekdays and commits the result (active once on the default branch).
Set the repository secret `ANTHROPIC_API_KEY` to have Claude phrase the cards; without it templates are used.

## Known limits
- Growth history comes from 30 US chip companies only; it is applied to other markets with a stated caveat.
- Price history uses today's company list, so companies that disappeared are missing.
- Thresholds (25%, 50%, top third) were chosen once, before looking at outcomes by threshold; do not tune them on results.
- Until claims come due (first: May 2027) there is no forward evidence, only history.
