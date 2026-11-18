"""Why did the price move? Classify a day's headlines with Jev, falling back to the keyword rules.

Always returns the same shape, so the site never depends on Jev:
  kind        report | analyst | deal | regulation | news   (same values as the rules in supply_chain/why.py)
  source      "jev" or "rules"
  confidence  Jev's probability for the kind (None for the rules)
  about       Jev's probability that the headlines are about this company itself (None for the rules)
  tone        -2..+2, how good or bad the headlines are for the company (None for the rules)
  rules_kind  what the keyword rules say (kept for comparison)
Jev's answer is used only when it is sure enough (MIN_CONF); otherwise the day is "news" (headlines that do not say why),
which is the honest answer. Headlines that are not about the company (about < 0.4) are also "news".
"""
from __future__ import annotations

from .jev import Jev, JevUnavailable

MIN_CONF = 0.6
KIND_OPTIONS = {
    "report": "The company's own quarterly or annual results, guidance or forecast",
    "analyst": "An analyst or bank upgraded, downgraded, or changed a price target or rating on the company",
    "deal": "A deal: acquisition, merger, stake, partnership, major contract or order",
    "regulation": "Government action: tariffs, export rules, sanctions, a probe, lawsuit, fine or new law",
    "news": "Other news, or the headlines do not say why the stock moved",
}
TONE = ["very negative for the company", "negative", "neutral", "positive", "very positive for the company"]
_client: Jev | None = None


def client() -> Jev:
    global _client
    if _client is None:
        _client = Jev()
    return _client


def classify(company: str, headlines: list[dict], rules_kind: str | None, jev: Jev | None = None) -> dict:
    out = {"kind": rules_kind, "source": "rules", "confidence": None, "about": None, "tone": None, "rules_kind": rules_kind}
    if not headlines:
        return out
    jev = jev or client()
    state = {"company": company, "headlines": [h.get("t", "") for h in headlines[:8]]}
    qs = {
        "about": {"type": "noul", "instructions": f"Are these headlines mainly about {company} itself, not only mentioning it in passing?"},
        "kind": {"type": "choice", "instructions": f"What most likely explains a big one-day move in {company}'s stock, according to these headlines?",
                 "criteria": KIND_OPTIONS},
        "tone": {"type": "score", "instructions": f"How good or bad are these headlines for {company}?", "criteria": TONE},
    }
    try:
        a = jev.ask(state, qs)
    except JevUnavailable as e:
        out["fallback_reason"] = str(e)
        return out
    conf = float(a["kind"].get("confidence") or a["kind"].get("probabilities", {}).get(a["kind"]["choice"], 0))
    about = a["about"]["noul"]
    kind = a["kind"]["choice"] if conf >= MIN_CONF and about >= 0.4 else "news"
    out.update(kind=kind, source="jev", confidence=round(conf, 3), about=round(about, 3), tone=round(a["tone"]["score"] - 2, 2))
    return out
