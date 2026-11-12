import json

from research.supply_chain import ledger, writer


def card():
    return {"id": "growth:X", "see": {"growth_pct": 60.0}, "past": {"cases": 85, "slowed_pct": 92.9}}


def draft(**kw):
    d = {k: "טקסט 60.0 ו-85" for k in writer.FIELDS}
    d.update(kw)
    return d


def test_model_text_with_a_new_number_is_rejected():
    assert writer._accept(card(), draft(), draft(see="צמחה ב-60.0"))
    assert not writer._accept(card(), draft(), draft(see="צמחה ב-61"))


def test_model_text_may_not_drop_or_invent_a_field():
    assert not writer._accept(card(), draft(), draft(past=""))
    assert not writer._accept(card(), draft(refute=""), draft(refute="משהו חדש"))


def test_ledger_detects_an_edit(tmp_path):
    p = tmp_path / "c.jsonl"
    for i in range(3):
        ledger._append(p, {"n": i})
    assert ledger.verify(p)
    rows = p.read_text().splitlines()
    r = json.loads(rows[1])
    r["n"] = 99
    rows[1] = json.dumps(r, ensure_ascii=False)
    p.write_text("\n".join(rows) + "\n")
    assert not ledger.verify(p)
