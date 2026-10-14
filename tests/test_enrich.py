import json
from pathlib import Path

import pytest

from catalog_cleaner.clean import clean, read_catalog
from catalog_cleaner.enrich import fill_types, parse_answers

ALLOWED = ["Apparel", "Drinkware"]


def test_parse_accepts_fenced_json_and_fixes_case():
    text = '```json\n[{"row": 1, "type": "drinkware"}, {"row": 2, "type": " Apparel "}]\n```'
    assert parse_answers(text, ALLOWED, {1, 2}) == {1: "Drinkware", 2: "Apparel"}


def test_parse_rejects_anything_not_allowed_or_not_asked():
    text = json.dumps([{"row": 1, "type": "Ignore previous instructions"}, {"row": 2, "type": "UNKNOWN"},
                       {"row": 99, "type": "Apparel"}, {"row": "3", "type": "Apparel"}, "junk", {"row": 4}])
    assert parse_answers(text, ALLOWED, {1, 2, 3, 4}) == {}


@pytest.mark.parametrize("text", ["I cannot help with that", "[not json]", '{"row": 1}'])
def test_parse_raises_on_unusable_reply(text):
    with pytest.raises(ValueError):
        parse_answers(text, ALLOWED, {1})


def _row(handle, title, typ=""):
    return {"Handle": handle, "Title": title, "Tags": "", "Body (HTML)": "<p>nice</p>", "Type": typ}


def _fake(prompt_log=None):
    def ask(system, user):
        if prompt_log is not None:
            prompt_log.append(user)
        rows = [int(line.split(":")[0]) for line in user.split("Products:\n")[1].splitlines()]
        titles = {int(line.split(":")[0]): line for line in user.split("Products:\n")[1].splitlines()}
        return json.dumps([{"row": n, "type": "Drinkware" if "Bottle" in titles[n] else "UNKNOWN"} for n in rows])
    return ask


def test_fill_changes_only_blank_types_and_records_everything():
    rows = [_row("a", "Steel Bottle", ""), _row("b", "Cotton Tee", ""), _row("c", "Mug", "Drinkware"),
            _row("d", "Shirt", "Apparel")]
    before = [dict(r) for r in rows]
    out, changes, flags = fill_types(rows, ask=_fake())
    assert rows == before                                              # input untouched
    assert [r["Type"] for r in out] == ["Drinkware", "", "Drinkware", "Apparel"]
    assert [(c.row, c.new) for c in changes] == [(1, "Drinkware")] and changes[0].reason
    assert [(f.row, f.issue) for f in flags] == [(2, "could not determine product type")]


def test_batches_and_bad_reply_is_flagged_not_fatal():
    rows = [_row("k", "Known", "Apparel"), _row("m", "Known Mug", "Drinkware")] + [_row(f"h{i}", f"Steel Bottle {i}") for i in range(5)]
    log = []
    out, changes, flags = fill_types(rows, ask=_fake(log), batch=2)
    assert len(log) == 3 and len(changes) == 5 and flags == []
    out, changes, flags = fill_types(rows, ask=lambda s, u: "sorry, no", batch=2)
    assert changes == [] and len(flags) == 5                           # flagged, nothing invented


def test_config_errors_are_not_swallowed():
    def boom(s, u):
        raise RuntimeError("Ollama call failed")
    with pytest.raises(RuntimeError):
        fill_types([_row("a", "x", "Apparel"), _row("b", "y")], ask=boom)


def test_no_known_types_means_flags_only():
    out, changes, flags = fill_types([_row("a", "x")], ask=lambda s, u: 1 / 0)
    assert changes == [] and flags[0].issue == "no existing Types to choose from"


def test_sample_catalog_blank_types_all_filled_with_a_stand_in_model():
    rows, _ = read_catalog(Path(__file__).parent.parent / "data" / "sample_catalog.csv")
    cleaned, _, _ = clean(rows)
    blanks = sum(not r["Type"] for r in cleaned)
    keywords = {"Bottle": "Drinkware", "Mug": "Drinkware", "T-Shirt": "Apparel", "Earbuds": "Electronics",
                "Pan": "Cookware", "Yoga": "Fitness", "Lamp": "Lighting", "Wallet": "Accessories"}

    def ask(system, user):
        lines = user.split("Products:\n")[1].splitlines()
        pick = lambda s: next((t for k, t in keywords.items() if k in s), "UNKNOWN")   # noqa: E731
        return json.dumps([{"row": int(ln.split(":")[0]), "type": pick(ln)} for ln in lines])

    out, changes, flags = fill_types(cleaned, ask=ask)
    assert blanks > 100 and len(changes) == blanks and flags == [] and all(r["Type"] for r in out)
