"""Turns a card's facts into plain Hebrew. Two writers, one contract.

template  always available. Every sentence is a fixed pattern filled with numbers from the card.
claude    used when the Anthropic SDK and credentials are present (TRENDVEST_WRITER=template turns it off).
          It gets the facts and the template text and may only rephrase. Its text is rejected, card by
          card, if it contains a number that is not in the card, or drops a field. The testable claim
          and the numbers are never written by the model.

Model text is cached by the card's facts, so an unchanged card is not paid for twice.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from . import graph as G

MODEL = "claude-opus-5-5"
CACHE = G.RESULTS / "inference_text.json"
FIELDS = ("title", "see", "past", "why", "who", "refute", "not")
MODE = "template"

STRENGTH = {"strong": "ההיסטוריה ברורה", "medium": "ההיסטוריה נוטה לכיוון הזה", "weak": "נטייה חלשה", "date": "תאריך ידוע, לא תחזית"}


def _names(xs: list[str]) -> str:
    return ", ".join(xs) if xs else "לא מופו"


def _changes(card: dict) -> str:
    return " ".join(f"{c['title']} ({c['status']})." for c in card["refute"])


def template(card: dict, market: dict) -> dict:
    n, s, p, d = card["name"], card["see"], card["past"], card["detector"]
    due = ".".join(str(int(x)) for x in reversed(card["claim"]["due"].split("-"))) if card["claim"] else None
    rhythm = f" הקצב בשלב \"{card['stage']}\": {card['stage_rhythm']}." if card["stage_rhythm"] else ""
    if d == "growth":
        other = "" if market["id"] == "chips" else " ההיסטוריה נמדדה על חברות שבבים. על השוק הזה עוד אין לנו מדידה משלו."
        return {
            "title": f"{n}: קצב הצמיחה הזה כנראה לא יחזיק",
            "see": f"ההכנסות של {n} גדלו ב-{s['growth_pct']}% לעומת התקופה המקבילה בשנה שעברה.",
            "past": f"מצאנו {p['cases']} מקרים דומים בעבר, ב-{p['companies']} חברות שבבים אמריקאיות שצמחו ב-{p['bucket_lo']}% ומעלה. "
                    f"ב-{p['slowed_pct']}% מהם הצמיחה הייתה נמוכה יותר שנה אחר כך, וב-{p['halved_pct']}% היא ירדה ליותר מחצי. "
                    f"הצמיחה החציונית שנה אחר כך: {p['median_later']}%. להשוואה: בכל המקרים, בלי קשר לקצב, הצמיחה האטה ב-{p['plain_pct']}%.{other}",
            "why": f"צמיחה חריגה מושכת מתחרים והרחבת ייצור, והשנה הבאה נמדדת מול מספר גבוה.{rhythm}",
            "who": f"אם ההזמנות של {n} יאטו, הספקים ירגישו ראשונים: {_names(card['suppliers'])}. הלקוחות: {_names(card['customers'])}.",
            "refute": f"צמיחה של {s['growth_pct']}% ומעלה גם בעוד שנה. " + (f"שינויים פתוחים בשלב הזה: {_changes(card)}" if card["refute"] else ""),
            "not": "זה לא אומר שההכנסות ירדו, וזה לא אומר לאן המניה תלך. האטה בצמיחה היא עדיין צמיחה.",
            "claim": f"עד {due}: צמיחת ההכנסות של {n} תהיה נמוכה מ-{s['growth_pct']}%.",
        }
    if d == "market_growth":
        b = " ".join(f"צמיחה של {x['lo']}%{' עד ' + str(x['hi']) + '%' if x['hi'] else ' ומעלה'} האטה שנה אחר כך ב-{x['slowed_pct']}% "
                     f"מ-{x['cases']} המקרים, והחציון ירד ל-{x['median_later']}%." for x in reversed(p["buckets"]))
        other = "" if market["id"] == "chips" else " ההיסטוריה נמדדה על חברות שבבים. על השוק הזה עוד אין לנו מדידה משלו."
        return {
            "title": f"{s['count']} מתוך {s['mapped']} חברות צומחות בקצב שבדרך כלל לא מחזיק",
            "see": f"ההכנסות של {s['count']} מתוך {s['mapped']} החברות שמיפינו גדלו ב-25% ומעלה בשנה האחרונה. החציון אצלן: {s['median_growth_pct']}%. "
                   "המהירות ביותר: " + ", ".join(f"{a} ({g}%)" for a, g in s["fastest"]) + ".",
            "past": f"{b} להשוואה: בכל המקרים, בלי קשר לקצב, הצמיחה האטה ב-{p['plain_pct']}%.{other}",
            "why": "כשחלק גדול מהשוק צומח מהר בבת אחת, המקור הוא בדרך כלל גל ביקוש אחד. כשהגל נחלש, הוא נחלש אצל כולם, "
                   "והשנה הבאה נמדדת מול מספרים גבוהים.",
            "who": "לפי שלב: " + ", ".join(f"{a} ({k})" for a, k in s["by_stage"]) + ".",
            "refute": "אם בעוד שנה רוב החברות האלה עדיין יצמחו באותו קצב או מהר יותר.",
            "not": "זה לא אומר שההכנסות ירדו, וזה לא אומר לאן המניות ילכו. האטה בצמיחה היא עדיין צמיחה.",
            "claim": f"רשמנו ביומן {s['count']} טענות נפרדות, אחת לכל חברה. בעוד שנה נספור כמה התקיימו.",
        }
    if d.startswith("price_"):
        up = card["claim"]["op"] == ">"
        was = "עלתה" if s["rel_year_pct"] > 0 else "ירדה"
        return {
            "title": f"{n}: אחרי שנה כזאת, המניה נטתה {'להמשיך להוביל' if up else 'לפגר'}",
            "see": f"בשנה האחרונה המניה של {n} {was} ב-{abs(s['rel_year_pct'])}% יותר מ{s['index'] or 'מדד השוק'}.",
            "past": f"מצאנו {p['cases']} מקרים דומים ב-{p['companies']} חברות. ב-{p['beat_index_pct']}% מהם המניה עקפה את המדד גם בחצי השנה שאחרי. "
                    f"להשוואה: מניה רגילה עוקפת את המדד ב-{p['plain_pct']}% מהמקרים. התוצאה החציונית מול המדד: {p['median_next']}%. "
                    "המדידה לא כוללת חברות שנמחקו מהמסחר.",
            "why": f"מהלך חד במחיר משקף ציפיות שכבר נכנסו למחיר.{rhythm}",
            "who": f"ספקים: {_names(card['suppliers'])}. לקוחות: {_names(card['customers'])}.",
            "refute": f"המניה {'תפגר אחרי' if up else 'תעקוף את'} המדד בחצי השנה הקרובה. " + _changes(card),
            "not": "זו נטייה סטטיסטית של קבוצה, לא הבטחה על מניה אחת.",
            "claim": f"עד {due}: המניה של {n} {'תעקוף את' if up else 'תפגר אחרי'} מדד השוק.",
        }
    if d == "vol":
        return {
            "title": f"{n}: המניה כנראה תישאר קופצנית",
            "see": f"בחצי השנה האחרונה המניה של {n} זזה בקצב שנתי של {s['vol_pct']}%. החציון בשוק הזה: {s['market_median_vol_pct']}%.",
            "past": f"בדקנו {p['cases']} מקרים של מניה שהייתה בשליש הקופצני של השוק שלה. ב-{p['stayed_pct']}% מהם היא נשארה שם גם בחצי השנה שאחרי. "
                    f"אם זה היה מקרי, היינו מצפים ל-{p['plain_pct']}%.",
            "why": "הסיבות שמקפיצות מניה לא נעלמות בחצי שנה: חוב, תלות בלקוח אחד, מוצר אחד, מחיר שנשען על ציפיות.",
            "who": f"מי שמחזיק את המניה. ספקים: {_names(card['suppliers'])}. לקוחות: {_names(card['customers'])}.",
            "refute": "חצי שנה רגועה, שבה המניה יוצאת מהשליש הקופצני של השוק.",
            "not": "זה לא אומר אם המניה תעלה או תרד. זה אומר שהדרך תהיה סוערת.",
            "claim": f"עד {due}: המניה של {n} תישאר בשליש הקופצני של השוק.",
        }
    v = "" if s["verified"] else " הפרט הזה עוד לא אומת מול מקור שני."
    return {
        "title": s["title"],
        "see": f"{s['detail']} מועד: {s['month']}. מצב: {s['status']}.{v}",
        "past": "אין כאן סטטיסטיקה. זה תאריך ידוע מראש, לא תחזית.",
        "why": f"השלב שמושפע: {card['stage']}.{rhythm}",
        "who": f"חברות בשלב הזה: {_names(card['exposed'])}.",
        "refute": "",
        "not": "אנחנו לא יודעים איך זה ייגמר. אנחנו יודעים מתי, ומי עומד ליד.",
        "claim": "",
    }


# ---------------------------------------------------------------- the model writer

SYSTEM = """You are the copy editor of a personal research tool that explains supply-chain markets to one private \
investor with no finance background. The reader is Israeli and reads Hebrew.

The tool finds unusual states with fixed rules and attaches what happened historically in similar states. \
You receive, for each card, the facts (JSON) and a Hebrew draft built from fixed sentence patterns. Your job is \
only to make each field read like a clear note from a knowledgeable friend: short sentences, everyday words, \
one idea per sentence. The draft is accurate but stiff; improve the wording, keep the meaning.

Constraints, each for a reason:
- Use only numbers that appear in that card's facts or draft, written the same way. Your text is checked by \
a program and a card with any other number is discarded. Do not compute, round or combine numbers.
- Do not add facts, causes, company names or forecasts that are not in the card. The reader must be able to \
trust that every statement traces back to data.
- No advice to buy, sell or hold, and no wording that implies certainty about a single stock. The tool shows \
tendencies of groups; the reader decides alone.
- Keep the caveats in "past" and "not". They are what keeps the card honest.
- Company names stay in Latin letters as given. Return every field for every card, in the same order, with the \
same id. An empty draft field stays empty."""


def _digits(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")))


def _key(card: dict, draft: dict) -> str:
    return hashlib.sha256(json.dumps([card["id"], card["see"], card["past"], draft], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _credentials() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or (Path.home() / ".config" / "anthropic").exists())


def _claude(todo: list[tuple[dict, dict]]) -> dict[str, dict]:
    import anthropic
    from pydantic import BaseModel

    class Card(BaseModel):
        id: str
        title: str
        see: str
        past: str
        why: str
        who: str
        refute: str
        not_: str

    class Cards(BaseModel):
        cards: list[Card]

    payload = [{"id": c["id"], "facts": {"see": c["see"], "past": c["past"], "stage": c["stage"]},
                "draft": {("not_" if k == "not" else k): d[k] for k in FIELDS}} for c, d in todo]
    client = anthropic.Anthropic()
    # Refusal fallback is on: if the model declines, the API reruns the request on a fallback model in the same call.
    with client.beta.messages.stream(
        model=MODEL, max_tokens=32000, system=SYSTEM,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "medium"}, output_format=Cards,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason != "end_turn" or msg.parsed_output is None:
        raise RuntimeError(f"model stopped with {msg.stop_reason}")
    out = {}
    for c in msg.parsed_output.cards:
        d = c.model_dump()
        d["not"] = d.pop("not_")
        out[c.id] = d
    return out


def _accept(card: dict, draft: dict, text: dict) -> bool:
    allowed = _digits(json.dumps([card["see"], card["past"]], ensure_ascii=False) + " ".join(draft.values()))
    for k in FIELDS:
        if bool(draft[k]) != bool(text.get(k)) or not _digits(text.get(k, "")) <= allowed:
            return False
    return True


def write_all(cards: list[dict], market: dict) -> None:
    global MODE
    drafts = [template(c, market) for c in cards]
    use_model = os.environ.get("TRENDVEST_WRITER", "auto") != "template" and _credentials()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    rejected = 0
    if use_model:
        todo = [(c, d) for c, d in zip(cards, drafts) if _key(c, d) not in cache]
        try:
            got = _claude(todo) if todo else {}
            for c, d in todo:
                if c["id"] in got and _accept(c, d, got[c["id"]]):
                    cache[_key(c, d)] = {k: got[c["id"]][k] for k in FIELDS}
                else:
                    rejected += 1
            MODE = f"claude ({rejected} rejected by the number check)" if rejected else "claude"
        except Exception as e:                                             # no SDK, no credit, network: the template still stands
            MODE = f"template (model unavailable: {type(e).__name__})"
        G.RESULTS.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    for c, d in zip(cards, drafts):
        by_model = use_model and _key(c, d) in cache
        c["text"] = {**d, **(cache[_key(c, d)] if by_model else {})}
        c["text"]["strength"] = STRENGTH[c["strength"]]
        c["written_by"] = "claude" if by_model else "template"
