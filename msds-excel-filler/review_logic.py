# -*- coding: utf-8 -*-
"""화학물질 도입검토 — 대상 판독 로직·기준 문안.

MSDS에서 추출한 물질명·구성성분을 기존 등록 이력과 비교해
도입검토 대상 여부와 정보등록 대상 여부를 자동 판독한다.
(판독 결과는 참고용이며, 최종 판단은 사내 절차에 따른다.)
"""
import re

# 프로그램 안에서 그대로 보여 주는 기준 설명 (사내 기준)
CRITERIA_REVIEW = [
    "공정(시설/장비 등)에서 취급하는 화학물질을 신규 도입하거나 다른 물질로 "
    "변경하고자 하는 경우 (단, 제조사 변경 등 구성성분이 동일한 경우는 제외 가능)",
    "도입검토 대상이 아닌 화학물질을 신규 도입하거나 변경하고자 하는 경우",
]
CRITERIA_REGISTER = [
    "공정(시설/장비 등)에서 취급하는 화학물질",
    "계측기, SWAS 시약 및 소화약제 등 당사 보유 시설/장비에서 취급하는 경우 포함",
    "협력업체가 반입하여 당사 시설/장비에 취급하는 경우(설비 세정약품 등)",
    "구성원이 작업 시 취급하는 화학물질(분석키트, 유/무상 샘플 등) "
    "(일반 소매점에서 일반 소비자 대상으로 판매되는 물질은 제외)",
    "단, 기존 등록 물질에서 제조사나 구성성분 및 함량의 변경이 없는 경우는 "
    "정보등록 대상이 아님",
]

_WS_RX = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS_RX.sub("", str(s or "")).lower()


def comp_key(components) -> tuple:
    """구성성분을 비교 가능한 키로 만든다 — CAS(없으면 성분명)+함유량."""
    keys = []
    for c in components or []:
        ident = _norm(c.get("cas") or "") or _norm(c.get("name") or "")
        if not ident:
            continue
        keys.append((ident, _norm(c.get("content") or "")))
    return tuple(sorted(keys))


def assess(name: str, components, db, consumer_product: bool = False,
           manufacturer: str = "") -> dict:
    """도입검토·정보등록 대상 여부를 판독한다.

    db: 기존 등록 목록 [{"name", "manufacturer", "components", ...}]
    consumer_product: 일반 소매점에서 일반 소비자 대상으로 판매되는 물질 여부
    manufacturer: 제조사 — 기존 등록과 제조사·구성성분이 모두 같으면
                  정보등록 대상이 아니다(변경 없음).
    반환: {"review": bool, "review_label", "review_reason",
           "register": bool, "register_label", "register_reason",
           "same_name": [기존 등록], "same_comp": [기존 등록]}
    """
    key = comp_key(components)
    nm = _norm(name)
    mf = _norm(manufacturer)
    same_name = [r for r in db or []
                 if nm and _norm(r.get("name")) == nm]
    same_comp = [r for r in db or []
                 if key and comp_key(r.get("components")) == key]
    # 제조사와 구성성분·함량이 모두 같은 기존 등록 (= 변경 없음)
    same_all = [r for r in same_comp if _norm(r.get("manufacturer")) == mf]

    if same_comp:
        review, review_label = False, "도입검토 제외 가능"
        review_reason = ("기존 등록 물질과 구성성분이 동일합니다"
                         "(제조사 변경 등 구성성분이 동일한 경우) — "
                         "도입검토를 제외할 수 있습니다.")
    elif same_name:
        review, review_label = True, "도입검토 대상"
        review_reason = ("같은 이름의 기존 등록 물질과 구성성분이 다릅니다 — "
                         "다른 물질로의 변경에 해당하여 도입검토 대상입니다.")
    else:
        review, review_label = True, "도입검토 대상"
        review_reason = ("기존 등록 이력이 없는 신규 도입 화학물질입니다 — "
                         "도입검토 대상입니다.")

    if consumer_product:
        register, register_label = False, "정보등록 제외"
        register_reason = ("일반 소매점에서 일반 소비자 대상으로 판매되는 "
                           "물질은 정보등록 대상에서 제외됩니다.")
    elif same_all:
        register, register_label = False, "정보등록 대상 아님"
        register_reason = ("기존 등록 물질에서 제조사와 구성성분 및 함량의 "
                           "변경이 없습니다 — 정보등록 대상이 아닙니다.")
    else:
        register, register_label = True, "정보등록 대상"
        register_reason = ("공정(시설/장비 등)·당사 보유 시설/장비·협력업체 반입·"
                           "구성원 작업 시 취급하는 화학물질은 정보등록 대상입니다.")

    return {"review": review, "review_label": review_label,
            "review_reason": review_reason,
            "register": register, "register_label": register_label,
            "register_reason": register_reason,
            "same_name": same_name, "same_comp": same_comp}


def components_text(components) -> str:
    """비교표에 넣을 '주요성분 및 함량' 문자열."""
    parts = []
    for c in components or []:
        name = (c.get("name") or "").strip() or "(성분명 미상)"
        cas = (c.get("cas") or "").strip()
        content = (c.get("content") or "").strip()
        s = name
        if cas:
            s += f" (CAS {cas})"
        if content:
            s += f" {content}"
        parts.append(s)
    return ", ".join(parts)
