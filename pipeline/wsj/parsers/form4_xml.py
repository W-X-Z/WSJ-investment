"""SEC Form 3/4/5 ownershipDocument XML → (filing header, rows).

스키마: https://www.sec.gov/info/edgar/ownershipxml.htm (X0609 기준). 값은 대부분 <tag><value>..</value></tag>
형태이고 각주는 <footnoteId id="F1"/> 로 붙는다.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from wsj.util import parse_date, to_bool, to_num


@dataclass
class Form4Parsed:
    header: dict[str, Any]
    rows: list[dict[str, Any]] = field(default_factory=list)


def _text(el: ET.Element | None, path: str) -> str | None:
    """path 끝에 value 가 있으면 그 텍스트, 없으면 요소 텍스트."""
    if el is None:
        return None
    node = el.find(path)
    if node is None:
        return None
    v = node.find("value")
    txt = (v.text if v is not None else node.text) or ""
    txt = txt.strip()
    return txt or None


def _footnotes(el: ET.Element | None) -> list[str]:
    if el is None:
        return []
    return sorted({f.get("id") for f in el.iter("footnoteId") if f.get("id")})


def _row(el: ET.Element, table_type: str, row_type: str, seq: int) -> dict[str, Any]:
    amounts = el.find("transactionAmounts")
    post = el.find("postTransactionAmounts")
    nature = el.find("ownershipNature")
    coding = el.find("transactionCoding")
    row: dict[str, Any] = {
        "seq": seq,
        "table_type": table_type,
        "row_type": row_type,
        "security_title": _text(el, "securityTitle"),
        "transaction_date": parse_date(_text(el, "transactionDate")),
        "deemed_execution_date": parse_date(_text(el, "deemedExecutionDate")),
        "transaction_form_type": _text(coding, "transactionFormType"),
        "transaction_code": _text(coding, "transactionCode"),
        "equity_swap_involved": to_bool(_text(coding, "equitySwapInvolved")),
        "transaction_timeliness": _text(el, "transactionTimeliness"),
        "shares": to_num(_text(amounts, "transactionShares")),
        "price_per_share": to_num(_text(amounts, "transactionPricePerShare")),
        "acquired_disposed": _text(amounts, "transactionAcquiredDisposedCode"),
        "shares_owned_following": to_num(_text(post, "sharesOwnedFollowingTransaction")),
        "ownership_nature": _text(nature, "directOrIndirectOwnership"),
        "indirect_ownership_text": _text(nature, "natureOfOwnership"),
        "conversion_or_exercise_price": None,
        "exercise_date": None,
        "expiration_date": None,
        "underlying_title": None,
        "underlying_shares": None,
        "footnote_ids": _footnotes(el),
    }
    if table_type == "derivative":
        under = el.find("underlyingSecurity")
        row.update(
            {
                "conversion_or_exercise_price": to_num(_text(el, "conversionOrExercisePrice")),
                "exercise_date": parse_date(_text(el, "exerciseDate")),
                "expiration_date": parse_date(_text(el, "expirationDate")),
                "underlying_title": _text(under, "underlyingSecurityTitle"),
                "underlying_shares": to_num(_text(under, "underlyingSecurityShares")),
            }
        )
        # 파생: 보유 행은 postTransactionAmounts 가 holding 바로 아래
        if row["shares_owned_following"] is None:
            row["shares_owned_following"] = to_num(_text(post, "sharesOwnedFollowingTransaction"))
    return row


def parse_form4(xml_text: str) -> Form4Parsed:
    root = ET.fromstring(xml_text)
    if root.tag != "ownershipDocument":
        raise ValueError(f"unexpected root {root.tag}")

    issuer = root.find("issuer")
    owners = []
    for ro in root.findall("reportingOwner"):
        rid = ro.find("reportingOwnerId")
        rel = ro.find("reportingOwnerRelationship")
        owners.append(
            {
                "cik": int(_text(rid, "rptOwnerCik") or 0) or None,
                "name": _text(rid, "rptOwnerName"),
                "is_director": to_bool(_text(rel, "isDirector")),
                "is_officer": to_bool(_text(rel, "isOfficer")),
                "is_ten_percent_owner": to_bool(_text(rel, "isTenPercentOwner")),
                "is_other": to_bool(_text(rel, "isOther")),
                "officer_title": _text(rel, "officerTitle"),
                "other_text": _text(rel, "otherText"),
            }
        )
    first = owners[0] if owners else {}
    footnotes = {f.get("id"): (f.text or "").strip() for f in root.findall("footnotes/footnote")}

    header = {
        "document_type": _text(root, "documentType"),
        "schema_version": _text(root, "schemaVersion"),
        "period_of_report": parse_date(_text(root, "periodOfReport")),
        "issuer_cik": int(_text(issuer, "issuerCik") or 0),
        "issuer_name": _text(issuer, "issuerName"),
        "issuer_ticker": _text(issuer, "issuerTradingSymbol"),
        "owner_cik": first.get("cik"),
        "owner_name": first.get("name"),
        "owner_count": len(owners),
        "is_director": first.get("is_director"),
        "is_officer": first.get("is_officer"),
        "is_ten_percent_owner": first.get("is_ten_percent_owner"),
        "is_other": first.get("is_other"),
        "officer_title": first.get("officer_title"),
        "aff10b5one": to_bool(_text(root, "aff10b5One")),
        "remarks": _text(root, "remarks"),
        "payload": {
            "owners": owners,
            "footnotes": footnotes,
            "not_subject_to_section16": _text(root, "notSubjectToSection16"),
        },
    }

    rows: list[dict[str, Any]] = []
    seq = 0
    for table_tag, table_type in (("nonDerivativeTable", "nonDerivative"), ("derivativeTable", "derivative")):
        table = root.find(table_tag)
        if table is None:
            continue
        for child in table:
            if child.tag.endswith("Transaction"):
                row_type = "transaction"
            elif child.tag.endswith("Holding"):
                row_type = "holding"
            else:
                continue
            seq += 1
            rows.append(_row(child, table_type, row_type, seq))
    return Form4Parsed(header=header, rows=rows)
