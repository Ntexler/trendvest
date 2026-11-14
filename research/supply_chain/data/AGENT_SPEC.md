# How to fill a market (instructions for a research agent)

You are filling one market into an existing research tool. Produce five files in
`research/supply_chain/data/<market>/`, with exactly the same structure as the finished reference market in
`research/supply_chain/data/chips/`. Read the reference files first and copy their schema field for field:
`companies.csv`, `edges.csv`, `events.csv`, `stages.json`, `market.json`. Also read `data/README.md`.
Do not modify anything outside your market folder. Do not run git.

1. `companies.csv` — columns `id,name,ticker,country,segment,tier,sites`. 45–70 companies of the chain across 5–7
   stages (tiers) that you define, in supply order (upstream first). `tier` is a short lower-case id; `segment` is what
   the company makes or does (companies that compete share a segment); `ticker` is the Yahoo Finance symbol on the home
   exchange; `country` is a 2-letter code; `sites` lists the main plants or operations. Then add 12–16 control
   companies (`tier` = `control`, `segment` = `control`): large unrelated companies from the same countries.
   VERIFY EVERY TICKER by downloading prices with yfinance; drop or fix any that returns no data; prefer companies with
   price history back to 2016. A company may also appear in another market's folder; that is fine.

2. `edges.csv` — supplier -> customer links between companies in your list. Columns exactly as in the reference:
   `supplier,customer,product,share_pct,share_year,evidence_type,confidence,evidence_year,valid_from,valid_from_basis,source_url,note,critical,critical_basis`.
   Aim for 50–100 links, but only links you can support: a company filing (10-K, 20-F, annual report — these name
   customers above 10% of revenue), an official supplier or customer list, a company press release, or reputable press.
   `share_pct` = share of the SUPPLIER's revenue from that customer when disclosed, else empty. `confidence`: high
   (filing or company statement), medium (reputable press), low (inferred or aggregator). `critical` = 1 when the
   CUSTOMER depends heavily on that supplier (sole or dominant source), with `critical_basis` = documented or judgment.
   `valid_from` = the year the link is known to exist, `valid_from_basis` = documented or assumed. Keep the comment
   lines at the top as in the reference.

3. `events.csv` — columns `id,name,ts_utc,timing_kind,location,hit,quality,confounder,source_url,note`. 12–20 dated
   shocks from 2016–2026 that hit this market (accidents, outages, recalls, bans, sanctions, tariffs, rulings, surprise
   product or regulatory news with market-wide effect). `ts_utc` is a precise ISO timestamp (when it happened, or when
   the news first became public — say which in `timing_kind`: event or news); `hit` = ids of the companies directly
   affected, separated by `;` (must exist in companies.csv); `quality` = best (clear surprise, precise time,
   identifiable companies), ok, or avoid (anticipated, slow, or confounded — name the confounder).

4. `stages.json` — keys `sources`, `stages`, `clock`, `calendar`, same shapes as the reference. Per stage: Hebrew
   `title`, `badge` (one line on the rhythm: how often and how long), `what` (2–3 plain sentences: what the stage does
   and what stops if it fails), `facts` (3–5 `[text, sourceKey]`: market size, concentration by country and company,
   margins), `pulse` (4–8 `[kind, text, sourceKey]`, kind = report / industry / press: how customers order and pay,
   contract lengths, lead times, backlog, pricing cadence, seasonality — with numbers), `choke` (1–5 weak points with
   shares). `clock`: 6–9 time constants `[what, how long, sourceKey]`. `calendar`: recurring data releases and events a
   learner can follow `[frequency, when, what, who publishes, sourceKey, verified 1/0]`. `sources`:
   `{key: [Hebrew label with publisher and date, url]}`.

5. `market.json` — same keys as the reference: `id`, `name` (Hebrew), `definition`, `checked` ("2026-11-11"), `intro`
   (2–3 plain sentences a complete beginner understands), `plain` (one simple sentence per stage, plural verbs),
   `plain_co` (the same sentence for one company, feminine singular), `time` (how long each stage takes, a few words),
   `kpis` (4 `[label, value, sourceKey]`), `tiers` (stage ids in order), `chain_title` (Hebrew heading for the chain),
   `index_name` (Hebrew name of a sector index or ETF to compare against) and `index_ticker` (Yahoo symbol, verified
   with yfinance), `lifecycle` (4–6 `[step, how long, stage id, one line, sourceKey]`) and `lifecycle_total`, `history`
   (8–12 `[year, title, what happened, stage id, sourceKey, event id or "", verified 1/0]`), `changes` (10–15 open
   items `[type, effect, stage id, title, detail, "YYYY-MM", status, sourceKey, verified 1/0]`; type = regulation /
   technology / move; effect = shortens / adds / delays / blocks / other), `event_he`
   (`{event id: [Hebrew name, one Hebrew sentence]}` for events not covered in `history`), `sources` (extra sources).

Writing rules for all Hebrew text: plain everyday Hebrew, short sentences, no jargon without a two-word explanation,
no metaphors, no marketing tone. Numbers with units. Company names in English.

Honesty rules: every factual claim needs a source you actually opened; if you only saw a search snippet, set verified
to 0 (or confidence low) and say so in `note`. Never invent a number, a link or a date. Fewer well-sourced items beat
many guesses. If a stage has little public evidence, say so in your report.

Before you finish: check that both JSON files parse, that the CSVs load with pandas (`comment="#"`), that every id
used in edges and events exists in companies.csv, that every source key used exists in `sources`, and that every
ticker returns price data.

Final message (short, in English, max 350 words): the stages you chose; counts (companies, links by confidence, events
by quality, history and change items); the 5 most important things a beginner should understand about this market;
what you could not verify; and any ticker or data problems.
