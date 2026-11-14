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

STRENGTH = {"strong": "קרה כמעט תמיד בעבר", "medium": "קרה ברוב המקרים בעבר", "weak": "נטייה חלשה", "date": "תאריך שידוע מראש"}

# The reader knows nothing about investing. So: no finance terms, whole numbers, "9 out of 10" instead of
# percentages, one idea per sentence, and every card says plainly what it does NOT mean.


def _names(xs: list[str]) -> str:
    return ", ".join(xs) if xs else "עוד לא מיפינו"


def _of10(pct: float) -> int:
    return round(pct / 10)


def _more(g: float) -> str:
    return f"פי {round(1 + g / 100, 1):g}" if g >= 100 else f"{round(g)}% יותר"


def template(card: dict, market: dict) -> dict:
    n, s, p, d = card["name"], card["see"], card["past"], card["detector"]
    due = ".".join(str(int(x)) for x in reversed(card["claim"]["due"].split("-"))) if card["claim"] else None
    other = "" if market["id"] == "chips" else " את הבדיקה עשינו על חברות שבבים, כי רק עליהן יש לנו מספיק נתונים. ייתכן שבתחום הזה זה שונה."
    slow_why = ("כשחברה מוכרת הרבה ומרוויחה הרבה, מתחרים נכנסים לשוק ומפעלים חדשים נבנים. "
                "חוץ מזה, אחרי שנה מצוינת קשה יותר לשבור שוב את השיא.")
    slow_not = "לגדול לאט יותר זה עדיין לגדול. זה לא אומר שהחברה בבעיה, וזה לא אומר אם המניה תעלה או תרד."
    if d == "growth":
        return {
            "title": f"{n} מוכרת הרבה יותר מבשנה שעברה. קצב כזה בדרך כלל לא נמשך",
            "see": f"{n} מכרה {_more(s['growth_pct'])} לעומת אותה תקופה בשנה שעברה. זה קצב גבוה מאוד.",
            "past": f"מצאנו {p['cases']} פעמים בעבר שבהן חברת שבבים גדלה בקצב כזה. ב-{_of10(p['slowed_pct'])} מכל 10 פעמים, "
                    f"שנה אחר כך היא גדלה לאט יותר. בדרך כלל הקצב ירד לסביבות {round(p['median_later'])}% בשנה.{other}",
            "why": slow_why,
            "who": f"אם {n} תזמין פחות, מי שמוכר לה ירגיש את זה ראשון: {_names(card['suppliers'])}. מי שקונה ממנה: {_names(card['customers'])}.",
            "refute": f"אם בעוד שנה {n} עדיין תגדל באותו קצב או מהר יותר, טעינו.",
            "not": slow_not,
            "claim": f"רשמנו: עד {due}, {n} תגדל לאט יותר מהיום. בתאריך הזה נבדוק אם צדקנו.",
        }
    if d == "market_growth":
        b = p["buckets"][-1]
        return {
            "title": f"{s['count']} מתוך {s['mapped']} חברות בתחום גדלות מהר מאוד. בדרך כלל זה לא נמשך",
            "see": f"{s['count']} מתוך {s['mapped']} החברות שאנחנו עוקבים אחריהן מכרו לפחות רבע יותר מבשנה שעברה. "
                   "הבולטות: " + ", ".join(a for a, _ in s["fastest"]) + ".",
            "past": f"מצאנו {b['cases']} פעמים בעבר שבהן חברת שבבים גדלה בקצב כזה. ב-{_of10(b['slowed_pct'])} מכל 10 פעמים, "
                    f"שנה אחר כך היא גדלה לאט יותר.{other}",
            "why": "כשהרבה חברות באותו תחום גדלות מהר בבת אחת, יש בדרך כלל סיבה אחת משותפת: כולם קונים עכשיו את אותו דבר. "
                   "כשהקנייה הזאת נרגעת, היא נרגעת אצל כולן.",
            "who": "איפה הן נמצאות בשרשרת: " + ", ".join(f"{a} ({k})" for a, k in s["by_stage"]) + ".",
            "refute": "אם בעוד שנה רוב החברות האלה עדיין יגדלו באותו קצב או מהר יותר, טעינו.",
            "not": slow_not,
            "claim": f"רשמנו {s['count']} בדיקות, אחת לכל חברה. בעוד שנה נספור בכמה מהן צדקנו.",
        }
    if d.startswith("price_"):
        up = card["claim"]["op"] == ">"
        return {
            "title": f"{n}: אחרי שנה כזאת, מניות נטו {'להמשיך לעלות יותר מהאחרות' if up else 'לעלות פחות מהאחרות'}",
            "see": f"בשנה האחרונה המניה של {n} {'עלתה הרבה יותר' if s['rel_year_pct'] > 0 else 'ירדה הרבה יותר'} משאר המניות בתחום.",
            "past": f"מצאנו {p['cases']} מקרים דומים. ב-{_of10(p['beat_index_pct'])} מכל 10, המניה עלתה יותר מהאחרות גם בחצי השנה שאחרי. "
                    "הבדיקה לא כוללת חברות שנסגרו, אז התמונה קצת ורודה מדי.",
            "why": "כשמחיר זז בחדות, הרבה מהחדשות הטובות או הרעות כבר נמצאות בתוכו.",
            "who": f"מי שמוכר לה: {_names(card['suppliers'])}. מי שקונה ממנה: {_names(card['customers'])}.",
            "refute": "אם בחצי השנה הקרובה יקרה ההפך, טעינו.",
            "not": "זו נטייה של קבוצת מניות, לא הבטחה על מניה אחת.",
            "claim": f"רשמנו: עד {due}, המניה של {n} {'תעלה יותר' if up else 'תעלה פחות'} משאר המניות בתחום. בתאריך הזה נבדוק.",
        }
    if d == "vol":
        return {
            "title": f"המחיר של {n} קופץ הרבה. כנראה שזה יימשך",
            "see": f"בחצי השנה האחרונה המחיר של המניה עלה וירד בחדות, בערך פי {round(s['vol_pct'] / s['market_median_vol_pct'], 1):g} ממניה רגילה בתחום.",
            "past": f"מצאנו {p['cases']} מקרים של מניות שקפצו כך. ב-{_of10(p['stayed_pct'])} מכל 10, הן המשיכו לקפוץ גם בחצי השנה שאחרי. "
                    f"אם זה היה סתם מזל, היינו רואים רק {_of10(p['plain_pct'])} מכל 10.",
            "why": "הסיבות שגורמות למחיר לקפוץ לא נעלמות מהר: חברה עם הרבה חובות, חברה שתלויה בלקוח אחד, או מניה שכולם מדברים עליה.",
            "who": "מי שמחזיק במניה כזאת צריך להיות מוכן לימים של ירידות חדות, גם אם בסוף היא עולה.",
            "refute": "אם בחצי השנה הקרובה המחיר יהיה רגוע, טעינו.",
            "not": "זה לא אומר אם המניה תעלה או תרד. זה אומר רק שהדרך תהיה סוערת.",
            "claim": f"רשמנו: עד {due}, המניה של {n} תמשיך להיות מהקופצניות בתחום. בתאריך הזה נבדוק אם צדקנו.",
        }
    v = "" if s["verified"] else " את הפרט הזה עוד לא בדקנו מול מקור נוסף."
    return {
        "title": s["title"],
        "see": f"{s['detail']} מצב: {s['status']}.{v}",
        "past": "כאן אין ניחוש. זה תאריך שידוע מראש.",
        "why": f"זה נוגע לשלב \"{card['stage']}\" בשרשרת.",
        "who": f"חברות שעובדות בשלב הזה: {_names(card['exposed'])}.",
        "refute": "",
        "not": "אנחנו לא יודעים איך זה ייגמר. אנחנו רק יודעים מתי זה קורה ומי קרוב לזה.",
        "claim": "",
    }


# ---------------------------------------------------------------- the model writer

SYSTEM = """You are the copy editor of a personal research tool that explains supply-chain markets to one private \
investor with no finance background. The reader is Israeli and reads Hebrew.

The tool finds unusual states with fixed rules and attaches what happened historically in similar states. \
You receive, for each card, the facts (JSON) and a Hebrew draft built from fixed sentence patterns. Your job is \
only to make each field read like a note from a friend to someone who has never invested: short sentences, everyday \
words, no finance terms (say "sold more" not "revenue growth", "the price jumps a lot" not "volatility"), one idea per \
sentence. The draft is already written at that level; keep it there and make it flow.

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
