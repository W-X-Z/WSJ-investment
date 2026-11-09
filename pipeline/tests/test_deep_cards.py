"""deep: 공시 고르기·문단 번호·구조 카드 정리·저장·변화 비교 (네트워크·모델 없음)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from wsj.deep import cards as K
from wsj.deep import diff as D
from wsj.deep import filings as F
from wsj.deep.kr_cards import to_card
from wsj.deep.target import clean_name

RID = re.compile(r"^[a-z0-9_:.-]{6,80}$")  # research.reports.report_id 검사(0040)와 같은 식


def _sub(rows: list[tuple[str, str, str, str]]) -> dict[str, Any]:
    """(form, filingDate, reportDate, items) → submissions JSON 모양."""
    keys = ["accessionNumber", "form", "filingDate", "reportDate", "primaryDocument", "items", "primaryDocDescription"]
    rec: dict[str, list[Any]] = {k: [] for k in keys}
    for i, (form, fd, rd, items) in enumerate(rows):
        rec["accessionNumber"].append(f"0000000000-26-{i:06d}")
        rec["form"].append(form)
        rec["filingDate"].append(fd)
        rec["reportDate"].append(rd)
        rec["primaryDocument"].append(f"doc{i}.htm")
        rec["items"].append(items)
        rec["primaryDocDescription"].append(form)
    return {"filings": {"recent": rec}}


def test_plan_picks_annuals_quarters_after_and_priority_8ks():
    sub = _sub([
        ("8-K", "2026-10-22", "2026-10-22", "5.02,9.01"),
        ("10-Q", "2026-11-05", "2026-09-30", ""),
        ("8-K", "2026-09-15", "2026-09-15", "2.02,9.01"),
        ("10-K", "2026-02-11", "2025-12-31", ""),
        ("10-Q", "2025-11-05", "2025-09-30", ""),   # 마지막 10-K 이전 → 제외
        ("8-K", "2026-01-05", "2026-01-05", "7.01"),
        ("8-K", "2025-12-20", "2025-12-20", "9.01"),  # 우선 항목 없음 → 제외
        ("10-K", "2025-02-07", "2024-12-31", ""),
        ("10-K", "2024-02-09", "2023-12-31", ""),
        ("10-K", "2023-02-09", "2022-12-31", ""),
    ])
    p = F.plan(sub, years=3, as_of=date(2026, 11, 9))
    assert [F.doc_key(f) for f in p["annual"]] == ["10-K FY2025", "10-K FY2024", "10-K FY2023"]
    assert p["registration"] == []
    assert [f.form for f in p["quarterly"]] == ["10-Q"] and p["quarterly"][0].file_date == date(2026, 11, 5)
    assert [f.file_date.isoformat() for f in p["eightks"]] == ["2026-10-22", "2026-09-15", "2026-01-05"]


def test_plan_adds_registration_when_few_annuals():
    sub = _sub([("10-K", "2026-09-15", "2026-06-30", ""), ("424B4", "2026-07-02", "", ""), ("S-1", "2026-01-20", "", "")])
    p = F.plan(sub, years=3, as_of=date(2026, 11, 9))
    assert len(p["annual"]) == 1 and [f.form for f in p["registration"]] == ["424B4"]


def test_paragraphs_merge_headings_and_split_long():
    text = "Overview\n\nWe make switchgear for data centers. " + ("x" * 50) + "\n\nShort\n\n" + ". ".join(["word " * 60] * 20)
    ps = F.paragraphs(text, max_len=800)
    assert ps[0].startswith("Overview — We make switchgear")
    assert all(len(p) <= 800 for p in ps)
    assert any(p.startswith("Short — ") for p in ps)


def _doc() -> F.Document:
    d = F.Document("10-K FY2026", "10-K", "0002080126-26-000035", date(2026, 9, 15), date(2026, 6, 30),
                   "https://www.sec.gov/x.htm")
    d.sections = {"item_1": "Business intro paragraph that is long enough to stand alone here.\n\n"
                            "Customer A accounted for 12% of net sales in fiscal 2026 and nothing else.",
                  "item_1a": "We depend on a single supplier of insulation materials for special transformers."}
    return d


def test_numbered_and_report_id():
    body, where, nxt = F.numbered(_doc())
    assert "[P1] Business intro" in body and "[P3] We depend" in body and nxt == 4
    assert where[2] == "10-K FY2026 Item 1 Business" and where[3] == "10-K FY2026 Item 1A Risk Factors"
    rid = K.report_id("us", "FPS", _doc())
    assert rid == "card:us:fps:fy2026" and RID.match(rid)
    reg = F.Document("424B4 2026-07-02", "424B4", "x", date(2026, 7, 2), None, "u")
    assert RID.match(K.report_id("us", "BRK.B", reg)) and K.report_id("us", "BRK.B", reg).endswith("424b4-2026-07-02")


def test_normalize_drops_items_without_valid_evidence_and_fills_customers():
    where = {1: "10-K FY2026 Item 1 Business", 2: "10-K FY2026 Item 1 Business", 3: "10-K FY2026 Item 1A Risk Factors"}
    raw = {
        "overview": {"summary": "배전 장비 제조사.", "segments": [{"name": "데이터센터", "detail": "매출 59%", "value": "59%",
                                                                   "evidence": [1]}]},
        "customers": {"empty": False, "summary": "10% 고객 1곳.", "items": [
            {"label": "10% 고객", "detail": "Customer A 12%", "name": "Customer A", "value": "12%", "evidence": [2]},
            {"label": "근거 없음", "detail": "x", "name": None, "value": None, "evidence": []},
            {"label": "범위 밖", "detail": "x", "name": None, "value": None, "evidence": [99]},
        ], "top_customers": [{"name": "Customer A", "share_pct": "12", "industry": None}], "top2_pct": None},
        "sourcing": '{"empty": false, "summary": "단일 공급", "items": [{"label": "단일 공급처", "detail": "절연재", '
                    '"name": null, "value": null, "evidence": ["P3"]}]}',
        "orders": {"empty": True, "summary": "", "items": []},
        "relations": [{"type": "customer", "name": "Customer A", "evidence": [2]}, {"type": "supplier", "name": "X", "evidence": []}],
    }
    card, missing = K.normalize(raw, where)
    assert [i["label"] for i in card["customers"]["items"]] == ["10% 고객"]
    assert card["customers"]["top_customers"][0]["share_pct"] == 12.0
    assert card["sourcing"]["items"][0]["evidence"] == [3]
    assert card["sourcing"]["items"][0]["loc"] == ["10-K FY2026 Item 1A Risk Factors"]
    assert card["orders"]["empty"] is True and "orders" not in missing
    assert set(missing) == {"dependencies", "competition", "pricing", "risks"}
    assert [r["name"] for r in card["relations"]] == ["Customer A"]
    assert card["overview"]["segments"][0]["label"] == "데이터센터"


class FakeLLM:
    def __init__(self, replies: list[dict[str, Any]]) -> None:
        self.replies = replies
        self.calls = 0

    def complete_json(self, system, user, model, repair, **kw):
        from wsj.briefs.llm import Completion

        r = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return r, [Completion(text="{}", model=model, input_tokens=50_000, output_tokens=4_000)]


class FakeStore:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.rpcs: list[tuple[str, dict[str, Any]]] = []

    def select(self, table, columns=None, filters=None, limit=None, order=None):
        return [r for r in self.rows if all(r.get(k) == v for k, v in (filters or {}).items())]

    def rpc(self, fn, args):
        self.rpcs.append((fn, args))
        return {"ok": len(args["rows"]), "rejected": []}


def _full_reply() -> dict[str, Any]:
    slot = {"empty": False, "summary": "s", "items": [{"label": "L", "detail": "d", "name": None, "value": "1", "evidence": [1]}]}
    return {s: slot for s in K.SLOTS}


def test_us_cards_extracts_saves_and_retries_on_missing_slots():
    llm = FakeLLM([{"customers": _full_reply()["customers"]}, _full_reply()])
    store = FakeStore()
    out = K.us_cards(llm, store, "FPS", "Forgent Power Solutions", [_doc()])
    assert llm.calls == 2                       # 첫 응답에 빠진 칸이 6개 → 한 번 더
    assert out["cards"][0]["missing"] == [] and out["cards"][0]["source"] == "llm"
    fn, args = store.rpcs[0]
    row = args["rows"][0]
    assert fn == "research.put_reports" and row["kind"] == "company" and row["report_id"] == "card:us:fps:fy2026"
    assert row["body"]["doc"]["accession_no"] == "0002080126-26-000035"
    assert out["usage_usd"] > 0


def test_us_cards_uses_cache_for_same_accession_and_skips_without_llm():
    body = {"doc": {"accession_no": "0002080126-26-000035"}, "card": {"customers": {}}, "missing": []}
    store = FakeStore([{"report_id": "card:us:fps:fy2026", "body": body}])
    out = K.us_cards(FakeLLM([_full_reply()]), store, "FPS", "Forgent", [_doc()])
    assert out["cards"][0]["source"] == "cache" and store.rpcs == []
    out2 = K.us_cards(None, FakeStore(), "FPS", "Forgent", [_doc()])
    assert out2["cards"] == [] and out2["skipped"][0]["report_id"] == "card:us:fps:fy2026"


def test_compare_and_profile():
    def card(items: dict[str, str | None], top2=None, rels=()):
        c = {s: {"empty": True, "items": []} for s in K.SLOTS}
        c["orders"] = {"empty": not items, "items": [{"label": k, "value": v, "detail": ""} for k, v in items.items()]}
        c["customers"] = {"empty": False, "items": [{"label": "10% 고객", "value": None}], "top2_pct": top2}
        c["relations"] = [{"type": "customer", "name": n} for n in rels]
        return c

    cards = [{"doc": {"key": "10-K FY2026"}, "card": card({"백로그 공시": "$3.0 billion", "선수금": "$264M"}, 30, ["Hyperscaler"])},
             {"doc": {"key": "10-K FY2025"}, "card": card({"백로그 공시": "$1.03 billion", "대형 계약": "x"}, 20)}]
    ch = D.compare(cards)[0]
    assert ch["from"] == "10-K FY2025" and ch["to"] == "10-K FY2026"
    o = ch["slots"]["orders"]
    assert o["changed"][0] == {"label": "백로그 공시", "from": "$1.03 billion", "to": "$3.0 billion", "detail": ""}
    assert [a["label"] for a in o["added"]] == ["선수금"] and [r["label"] for r in o["removed"]] == ["대형 계약"]
    assert ch["slots"]["customers"]["top2_pct"] == {"from": 20, "to": 30}
    assert ch["relations"]["added"][0]["name"] == "Hyperscaler"
    prof = D.profile(cards, target={"symbol": "FPS", "price": {"close": 25.8}, "junk": None})
    assert prof["years"] == ["10-K FY2026", "10-K FY2025"] and "조달" in prof["empty_slots"]
    assert prof["target"] == {"symbol": "FPS", "price": {"close": 25.8}}


def test_kr_card_shape_matches_us():
    raw = {"cards": {"customers": {"summary": "현대차 납품", "items": [{"label": "계열사 납품", "detail": "d", "evidence": [3]}],
                                   "top2_pct": 80}},
           "empty_slots": ["orders"], "relations": [{"edge_type": "supply_contract", "src_name": "A", "dst_name": "B",
                                                     "rcept_no": "2026"}]}
    c = to_card(raw)
    assert set(K.SLOTS) <= set(c) and c["customers"]["top2_pct"] == 80 and c["orders"]["empty"] is True
    assert c["sourcing"]["empty"] is True and c["relations"][0]["type"] == "supply_contract"


def test_clean_name():
    assert clean_name("Centrus Energy Corp. Class A Common Stock") == "Centrus Energy Corp."
    assert clean_name("Forgent Power Solutions, Inc. Class A Common Stock") == "Forgent Power Solutions, Inc."
    assert clean_name("NVIDIA Corporation") == "NVIDIA Corporation"
