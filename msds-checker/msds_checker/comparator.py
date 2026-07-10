"""연도별 MSDS 레코드를 비교해 제조사/성분 변경 여부를 판정한다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import Ingredient, MsdsRecord, normalize_company

UNKNOWN = "판정불가"
CHANGED = "변경"
UNCHANGED = "변경없음"


@dataclass
class IngredientDiff:
    added: list[Ingredient] = field(default_factory=list)
    removed: list[Ingredient] = field(default_factory=list)
    # (이전, 이후) 쌍: 같은 성분인데 함유량 표기가 달라진 경우
    content_changed: list[tuple[Ingredient, Ingredient]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed or self.content_changed)


@dataclass
class YearComparison:
    year_from: int
    year_to: int
    record_from: MsdsRecord
    record_to: MsdsRecord
    manufacturer_verdict: str = UNKNOWN  # 변경 / 변경없음 / 판정불가
    manufacturer_detail: str = ""
    ingredient_verdict: str = UNKNOWN
    ingredient_diff: IngredientDiff = field(default_factory=IngredientDiff)


def _normalize_content(content: str) -> str:
    """함유량 표기를 비교 가능한 형태로 정규화. '10 - 20 %' == '10~20%'"""
    s = content.strip().lower().replace("%", "")
    s = re.sub(r"[~–]", "-", s)
    s = re.sub(r"\s+", "", s)
    s = s.replace("balance", "잔량")
    return s


def compare_ingredients(prev: list[Ingredient], curr: list[Ingredient]) -> IngredientDiff:
    diff = IngredientDiff()
    prev_map = {i.key(): i for i in prev}
    curr_map = {i.key(): i for i in curr}
    for key, ing in curr_map.items():
        if key not in prev_map:
            diff.added.append(ing)
    for key, ing in prev_map.items():
        if key not in curr_map:
            diff.removed.append(ing)
    for key in prev_map.keys() & curr_map.keys():
        a, b = prev_map[key], curr_map[key]
        if a.content and b.content and _normalize_content(a.content) != _normalize_content(b.content):
            diff.content_changed.append((a, b))
    return diff


def compare_records(prev: MsdsRecord, curr: MsdsRecord) -> YearComparison:
    comp = YearComparison(
        year_from=prev.year or 0,
        year_to=curr.year or 0,
        record_from=prev,
        record_to=curr,
    )

    # 제조사 판정
    if prev.manufacturer and curr.manufacturer:
        if normalize_company(prev.manufacturer) == normalize_company(curr.manufacturer):
            comp.manufacturer_verdict = UNCHANGED
            comp.manufacturer_detail = f"동일: {curr.manufacturer}"
        else:
            comp.manufacturer_verdict = CHANGED
            comp.manufacturer_detail = f"{prev.manufacturer} → {curr.manufacturer}"
    else:
        comp.manufacturer_verdict = UNKNOWN
        missing = []
        if not prev.manufacturer:
            missing.append(str(prev.year))
        if not curr.manufacturer:
            missing.append(str(curr.year))
        comp.manufacturer_detail = f"{', '.join(missing)}년 문서에서 제조사를 찾지 못함"

    # 성분 판정
    if prev.ingredients and curr.ingredients:
        comp.ingredient_diff = compare_ingredients(prev.ingredients, curr.ingredients)
        comp.ingredient_verdict = CHANGED if comp.ingredient_diff.changed else UNCHANGED
    else:
        comp.ingredient_verdict = UNKNOWN

    return comp


def group_by_year(records: list[MsdsRecord]) -> tuple[dict[int, MsdsRecord], list[str]]:
    """연도 → 대표 레코드. 같은 연도에 여러 파일이 있으면 경고를 남기고 마지막 파일을 쓴다."""
    grouped: dict[int, MsdsRecord] = {}
    warnings: list[str] = []
    for rec in records:
        if rec.year is None:
            warnings.append(f"연도 미상이라 제외됨: {rec.filename}")
            continue
        if rec.year in grouped:
            warnings.append(
                f"{rec.year}년 문서가 2개 이상입니다. '{rec.filename}'을(를) 사용합니다."
            )
        grouped[rec.year] = rec
    return grouped, warnings


def compare_all(records: list[MsdsRecord]) -> tuple[list[YearComparison], list[str]]:
    """연도 오름차순으로 인접 연도끼리 비교한 결과 목록과 경고를 반환."""
    grouped, warnings = group_by_year(records)
    years = sorted(grouped)
    comparisons = [
        compare_records(grouped[years[i]], grouped[years[i + 1]])
        for i in range(len(years) - 1)
    ]
    if len(years) < 2:
        warnings.append("비교하려면 서로 다른 연도의 MSDS가 2개 이상 필요합니다.")
    return comparisons, warnings


# ---------------------------------------------------------------- 보고서

def _fmt_ing(i: Ingredient) -> str:
    parts = [i.name or "(이름 미상)", f"CAS {i.cas}" if i.cas else ""]
    if i.content:
        parts.append(f"함유량 {i.content}")
    return " / ".join(p for p in parts if p)


def build_report(records: list[MsdsRecord], comparisons: list[YearComparison],
                 warnings: list[str]) -> str:
    lines: list[str] = ["=== MSDS 연도별 변경 판정 보고서 ===", ""]

    lines.append("[분석 대상]")
    for rec in sorted(records, key=lambda r: (r.year or 0, r.filename)):
        y = rec.year if rec.year is not None else "미상"
        lines.append(f"  {y}년  {rec.filename}")
        if rec.product:
            lines.append(f"        제품명: {rec.product}")
        lines.append(f"        제조사: {rec.manufacturer or '(추출 실패)'}")
        lines.append(f"        성분 {len(rec.ingredients)}종: "
                     + ", ".join(_fmt_ing(i) for i in rec.ingredients))
        for w in rec.warnings:
            lines.append(f"        ⚠ {w}")
    lines.append("")

    lines.append("[연도별 판정]")
    if not comparisons:
        lines.append("  (비교할 연도 쌍이 없습니다)")
    for c in comparisons:
        lines.append(f"  ● {c.year_from}년 → {c.year_to}년")
        lines.append(f"    - 제조사: {c.manufacturer_verdict}  ({c.manufacturer_detail})")
        lines.append(f"    - 성분:   {c.ingredient_verdict}")
        d = c.ingredient_diff
        for i in d.added:
            lines.append(f"        + 추가: {_fmt_ing(i)}")
        for i in d.removed:
            lines.append(f"        - 삭제: {_fmt_ing(i)}")
        for a, b in d.content_changed:
            lines.append(
                f"        ~ 함유량 변경: {b.name or b.cas}  {a.content} → {b.content}"
            )
        if c.ingredient_verdict == UNCHANGED:
            lines.append("        (성분 구성과 함유량이 동일)")
    lines.append("")

    if warnings:
        lines.append("[주의]")
        for w in warnings:
            lines.append(f"  ⚠ {w}")

    return "\n".join(lines)


def build_csv(comparisons: list[YearComparison]) -> str:
    """엑셀에서 열 수 있는 요약 CSV(UTF-8 BOM은 저장 시 추가)."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["기준연도", "비교연도", "제조사 판정", "제조사 상세",
                "성분 판정", "추가 성분", "삭제 성분", "함유량 변경"])
    for c in comparisons:
        d = c.ingredient_diff
        w.writerow([
            c.year_from, c.year_to,
            c.manufacturer_verdict, c.manufacturer_detail,
            c.ingredient_verdict,
            "; ".join(_fmt_ing(i) for i in d.added),
            "; ".join(_fmt_ing(i) for i in d.removed),
            "; ".join(f"{b.name or b.cas}: {a.content}→{b.content}"
                      for a, b in d.content_changed),
        ])
    return buf.getvalue()
