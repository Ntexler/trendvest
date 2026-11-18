# Company story cards: research spec

Goal: a private person with zero investing knowledge opens a company and, in two minutes, knows where it is,
what it does, how it started, who runs it, who owns it, and how to start following it.

## Output
One file per group: `research/supply_chain/data/stories/<group>.json`, an object keyed by ticker (exactly as in
`targets.json`). Write it incrementally (after every few companies) so work is not lost.

```json
{
  "4063.T": {
    "name": "Shin-Etsu Chemical",
    "checked": "2026-11-12",
    "one_liner": "משפט אחד: מה החברה עושה ולמי, במילים של מי שלא מבין כלום בהשקעות",
    "hq": {"city": "טוקיו", "country": "יפן"},
    "founded": 1926,
    "employees": {"value": 28239, "year": 2025, "src": "yahoo"},
    "founders": [{"name": "...", "story": "1-2 משפטים: מי היו ואיך זה התחיל", "src": ["W"]}],
    "timeline": [[1926, "...", ["W"]], [2001, "...", ["AR"]]],
    "leaders": [{"name": "...", "role": "מנכ\"ל", "since": 2019, "background": "חצי משפט", "src": ["AR"]}],
    "governance": [{"text": "המנכ\"ל הוא גם יו\"ר הדירקטוריון", "src": ["yahoo"]}],
    "owners": {"text": "מי מחזיק: משפחת המייסד / המדינה / קרנות מחקות מדד", "src": ["..."]},
    "approach": {"text": "הגישה הארגונית, רק אם יש מקור אמין (דוח שנתי, מכתב המנכ\"ל, ספר או כתבה רצינית)", "src": ["..."]},
    "how_to_start": ["מה היא מוכרת ולמי", "במה המחיר שלה תלוי", "מה לעקוב: מתי הדוח הבא, איזה נתון חודשי"],
    "sources": {"W": ["Wikipedia: Shin-Etsu Chemical", "https://en.wikipedia.org/wiki/Shin-Etsu_Chemical"], "yahoo": ["Yahoo Finance profile", "https://finance.yahoo.com/quote/4063.T/profile"]},
    "unverified": ["פרט שלא הצלחת לאמת מול מקור שני"]
  }
}
```

`approach` may be `null`. Any other field you cannot source: leave it out and say so in `unverified`.

## Rules
- Every fact has a `src`. No source, no fact. Never invent numbers, dates, names or quotes.
- Prefer primary sources: the company's own site and annual report, filings (SEC EDGAR full-text search
  https://efts.sec.gov/LATEST/search-index?q=...&forms=10-K works; www.sec.gov pages may refuse scripts), then
  Wikipedia, then serious press. Yahoo officers/holders for the company are already in
  `research/supply_chain/data/<market>/profiles.json` under the company id (see `targets.json`); use them.
- Hebrew, plain words, short sentences, one idea per sentence. No finance terms (say "מוכרת" not "הכנסות",
  "בעלת השליטה" is fine, explain anything harder in the same sentence). Names of people and companies stay in
  Latin letters. Write numbers with digits.
- Neutral tone. No praise, no advice, no "מבטיחה", "מובילה בעולם" unless a source says so with a number.
- `governance` items are facts a novice should notice: CEO also chair, founder or family control, state
  ownership, dual-class shares, recent CEO change, big lawsuit or sanction. Each with a source.
- `how_to_start[2]`: when the next report is expected, from the company's investor-relations calendar if published,
  else "בדרך כלל ב<חודש>, לפי השנים הקודמות" and say it is an estimate.
- Length: one_liner ≤ 25 words; founders story ≤ 40 words each; timeline 4-7 items ≤ 25 words each.
- If a ticker turns out to be wrong or the company is not listed, write `{"name": ..., "problem": "..."}`.
