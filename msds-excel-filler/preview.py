# -*- coding: utf-8 -*-
"""편집 중인 MsdsData를 엑셀 양식과 같은 모양의 HTML 미리보기로 만든다.

색상은 assets/template.xlsx 실제 셀 서식에서 가져온 값이다:
제목 #FF0000, 항목 헤더 #FFFF00, 제품명·하단 안내 #D7E4BD(테마6 tint 0.6),
응급조치 소제목 #F2DCDB(테마5 tint 0.8).
"""
import base64
import html
import os
from functools import lru_cache

from excel_writer import GHS_DIR, split_two

_RED = "#FF0000"
_YELLOW = "#FFFF00"
_GREEN = "#D7E4BD"
_PINK = "#F2DCDB"

_BASE = ("border:1px solid #000;padding:4px 6px;"
         "font-family:'Malgun Gothic','맑은 고딕',sans-serif;color:#000;")


@lru_cache(maxsize=16)
def _pic_b64(code: str) -> str:
    path = os.path.join(GHS_DIR, f"{code}.png")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _td(text, colspan=1, rowspan=1, bg="", bold=False, size=11,
        align="center", extra=""):
    style = _BASE + f"font-size:{size}px;text-align:{align};vertical-align:middle;"
    if bg:
        style += f"background:{bg};"
    if bold:
        style += "font-weight:bold;"
    return (f'<td colspan="{colspan}" rowspan="{rowspan}" '
            f'style="{style}{extra}">{text}</td>')


def _bullets_html(items):
    lines = [f"▶ {html.escape(s)}" for s in items if s.strip()]
    return "<br>".join(lines) or "&nbsp;"


def _two_col_row(items, min_height=60):
    left, right = split_two(items)
    ex = f"height:{min_height}px;"
    return ("<tr>"
            + _td(_bullets_html(left), colspan=3, align="left", extra=ex)
            + _td(_bullets_html(right), colspan=3, align="left", extra=ex)
            + "</tr>")


def _header_row(title, size=14):
    return "<tr>" + _td(html.escape(title), colspan=6, bg=_YELLOW,
                        bold=True, size=size) + "</tr>"


def preview_html(rec) -> str:
    """MsdsData(또는 동일 필드를 가진 객체) → 양식 미리보기 HTML."""
    pics = ""
    for code in list(dict.fromkeys(rec.pictograms))[:6]:
        b64 = _pic_b64(code)
        if b64:
            pics += (f'<img src="data:image/png;base64,{b64}" '
                     f'style="width:64px;height:64px;margin:2px 6px;">')
    pics = pics or "&nbsp;"

    product = html.escape(rec.product_name or "").replace("\n", "<br>") or "&nbsp;"
    signal = html.escape(rec.signal_word or "") or "&nbsp;"

    rows = []
    rows.append("<tr>" + _td("화학물질 작업공정별 관리 요령", colspan=6, bg=_RED,
                             bold=True, size=20,
                             extra="color:#fff;height:44px;") + "</tr>")
    rows.append("<tr>"
                + _td("제품명", colspan=2, bg=_YELLOW, bold=True, size=14)
                + _td(pics, colspan=3, rowspan=2)
                + _td("신호어", bg=_YELLOW, bold=True, size=12) + "</tr>")
    rows.append("<tr>"
                + _td(product, colspan=2, bg=_GREEN, bold=True, size=12,
                      extra="height:64px;")
                + _td(signal, bold=True, size=12) + "</tr>")

    rows.append(_header_row("건강 및 환경에 대한 유해성, 물리적 위험성"))
    rows.append(_two_col_row(rec.hazards))

    rows.append(_header_row("안전 및 보건상의 취급주의 사항"))
    rows.append(_two_col_row(rec.precautions))

    rows.append(_header_row("적절한 보호구"))
    rows.append("<tr>" + _td(_bullets_html(rec.ppe), colspan=6, align="left",
                             extra="height:60px;") + "</tr>")

    rows.append(_header_row("응급조치 요령 및 사고 시 대처방법"))
    rows.append("<tr>" + _td("흡입시", colspan=3, bg=_PINK, bold=True, size=12)
                + _td("피부 또는 눈 접촉시", colspan=3, bg=_PINK, bold=True,
                      size=12) + "</tr>")
    rows.append("<tr>"
                + _td(_bullets_html(rec.inhalation), colspan=3, align="left",
                      extra="height:80px;")
                + _td(_bullets_html(rec.skin_eye), colspan=3, align="left",
                      extra="height:80px;") + "</tr>")
    rows.append("<tr>" + _td("먹었을 때", colspan=3, bg=_PINK, bold=True, size=12)
                + _td("응급대응", colspan=3, bg=_PINK, bold=True, size=12)
                + "</tr>")
    rows.append("<tr>"
                + _td(_bullets_html(rec.ingestion), colspan=3, align="left",
                      extra="height:80px;")
                + _td(_bullets_html(rec.emergency), colspan=3, align="left",
                      extra="height:80px;") + "</tr>")
    rows.append("<tr>" + _td("상세한 내용은 MSDS 원본을 참조하시길 바랍니다",
                             colspan=6, bg=_GREEN, bold=True, size=12) + "</tr>")

    return ('<table style="border-collapse:collapse;width:100%;'
            'table-layout:fixed;background:#fff;">'
            + "".join(rows) + "</table>")
