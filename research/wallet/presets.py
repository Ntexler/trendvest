"""Broker presets for the wallet page, built from the researched fees_il.json.

    python -m research.wallet.presets    -> map/site/data/wallet_fees.json
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "supply_chain" / "map" / "site" / "data" / "wallet_fees.json"
HE = {"ibkr": "Interactive Brokers", "interactive_il": "אינטראקטיב ישראל", "meitav_trade": "מיטב טרייד", "ibi_smart": "IBI Smart",
      "excellence": "אקסלנס", "altshuler_trade": "אלטשולר שחם טרייד", "leumi": "בנק לאומי", "hapoalim": "בנק הפועלים"}


def main() -> None:
    f = json.loads((HERE / "fees_il.json").read_text())
    out = []
    for b in f["brokers"]:
        us = b.get("us") or {}
        c_us = {"per_share": us.get("per_share"), "pct": us.get("pct"), "min": us.get("min"), "max_pct": us.get("max_pct"), "cur": "USD"}
        ta = b.get("tase")
        c_ta = {"pct": ta["pct"], "min": ta.get("min_ils"), "cur": "ILS"} if ta else None
        eu = b.get("eu")
        c_other = {"pct": eu["pct"], "min": (eu.get("min") or {}).get("EUR"), "cur": "EUR"} if eu else dict(c_us)
        fx = b.get("fx_fee_pct")
        if fx is None and isinstance(b.get("fx"), dict):
            fx = b["fx"].get("pct")
        out.append({"id": b["id"], "name": HE.get(b["id"], b["name"]), "commission": {"US": c_us, "TA": c_ta, "other": c_other},
                    "fx_pct": fx or 0, "custody": b.get("custody"), "other_assumed": not eu,
                    "note": " ".join(x for x in [us.get("note"), b.get("note")] if x)[:300]})
    OUT.write_text(json.dumps({"checked": f["checked"], "brokers": out, "service_fee_examples": f["service_fee_examples"]}, ensure_ascii=False))
    print(len(out), "presets ->", OUT)


if __name__ == "__main__":
    main()
