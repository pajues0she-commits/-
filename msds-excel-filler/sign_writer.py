# -*- coding: utf-8 -*-
"""유해화학물질 규격 표지판(시안) SVG 생성.

화학물질관리법 시행규칙 [별표 2] "유해화학물질의 표시방법(제12조제2항 관련)"
1호(보관·저장시설 또는 진열·보관 장소 표지) 양식을 따른다.

규격(별표 2 1호 나목, a=50cm 기준):
  a = 50cm (표지판 높이),  b = (3/2)a = 75cm (너비)
  c = (1/4)a = 12.5cm ("유해화학물질" 글자 테두리 높이)
  d = (1/4)a = 12.5cm (관리책임자·비상전화 테두리 높이)
  글자 크기: "유해화학물질" 글자 높이는 테두리(c) 전체 높이의 65% 이상
  색상: 바탕 흰색, 테두리 검정, "유해화학물질" 글자 빨강,
        관리책임자·비상전화 글자 검정
하단에는 물질명·국제연합번호·그림문자 표를 둔다(같은 호 양식 그림).

SVG 좌표 단위는 mm(1단위 = 1mm)이고 문서 크기를 cm로 지정하므로
실측 크기로 인쇄·출력할 수 있다.
"""
import base64
import html
import os
from functools import lru_cache

from excel_writer import GHS_DIR

# 별표 2 규격 (mm)
A_MM = 500.0            # a = 50cm
B_MM = A_MM * 3 / 2     # b = 75cm
C_MM = A_MM / 4         # c = 12.5cm
D_MM = A_MM / 4         # d = 12.5cm

_FONT = "'Malgun Gothic','맑은 고딕',sans-serif"


@lru_cache(maxsize=16)
def _pic_b64(code: str) -> str:
    path = os.path.join(GHS_DIR, f"{code}.png")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _text_units(s: str) -> float:
    """개략적인 글자폭(한글 1.0em, 영문·숫자 0.55em)."""
    return sum(1.0 if ord(ch) > 0x2E80 else 0.55 for ch in s)


def build_sign_svg(entries, manager: str = "", phone: str = "",
                   phone2: str = "") -> str:
    """규격 표지판 SVG 문자열을 만든다.

    entries: [{"name": 물질명, "un": 국제연합번호, "pictograms": ["GHS05",...]}]
    manager/phone/phone2: 관리책임자 성명 / 비상전화 / 보조 연락처(선택)
    """
    esc = html.escape
    rows = list(entries) or [{}]
    if len(rows) < 4:                      # 별표 2 양식 그림과 같이 최소 4행
        rows = rows + [{}] * (4 - len(rows))

    col_w = [300.0, 180.0, 270.0]          # 물질명 | 국제연합번호 | 그림문자
    col_x = [0.0, col_w[0], col_w[0] + col_w[1]]
    head_h, row_h = 45.0, 70.0
    gap_panel_table = 30.0
    table_y = A_MM + gap_panel_table
    total_h = table_y + head_h + row_h * len(rows)

    p = []          # SVG 조각들
    # ── 상단 표지판 (b × a) ──────────────────────────────
    p.append(f'<rect x="3" y="3" width="{B_MM-6}" height="{A_MM-6}" '
             f'fill="#ffffff" stroke="#000000" stroke-width="6"/>')

    gap = (A_MM - C_MM - D_MM) / 3          # 상·중·하 여백 균등
    box_x, box_w = 40.0, B_MM - 80.0

    # "유해화학물질" 테두리(c) — 글자 높이 ≥ 0.65c (font 90mm ≈ 0.72c)
    ty = gap
    p.append(f'<rect x="{box_x}" y="{ty}" width="{box_w}" height="{C_MM}" '
             f'fill="#ffffff" stroke="#000000" stroke-width="4"/>')
    title = "유해화학물질"
    fs = 90.0
    pad = 34.0
    start = box_x + pad + fs / 2
    end = box_x + box_w - pad - fs / 2
    step = (end - start) / (len(title) - 1)
    for i, ch in enumerate(title):
        p.append(f'<text x="{start + step * i:.1f}" y="{ty + C_MM / 2:.1f}" '
                 f'font-family="{_FONT}" font-size="{fs}" font-weight="700" '
                 f'fill="#FF0000" text-anchor="middle" '
                 f'dominant-baseline="central">{esc(ch)}</text>')

    # 관리책임자·비상전화 테두리(d) — 글자 검정
    by = gap * 2 + C_MM
    p.append(f'<rect x="{box_x}" y="{by}" width="{box_w}" height="{D_MM}" '
             f'fill="#ffffff" stroke="#000000" stroke-width="4"/>')
    l1 = f"관리책임자 : {manager.strip() or 'ㅇㅇㅇ'} (성명)"
    l2 = f"비상전화 : {phone.strip() or '00-000-0000'}"
    l3 = f"({phone2.strip()}) (연락처)" if phone2.strip() else ""
    tx = box_x + 30
    cfs = 30.0
    lines = [l1, l2] + ([l3] if l3 else [])
    if len(lines) == 2:
        ys = [by + D_MM * 0.34, by + D_MM * 0.70]
    else:
        ys = [by + D_MM * 0.26, by + D_MM * 0.54, by + D_MM * 0.82]
    for line, y in zip(lines, ys):
        x = tx + (110 if line is l3 else 0)     # 보조 연락처는 번호 밑에 들여쓰기
        p.append(f'<text x="{x}" y="{y:.1f}" font-family="{_FONT}" '
                 f'font-size="{cfs}" font-weight="700" fill="#000000" '
                 f'dominant-baseline="central">{esc(line)}</text>')

    # ── 하단 표: 물질명 | 국제연합번호 | 그림문자 ─────────
    p.append(f'<rect x="2" y="{table_y}" width="{B_MM-4}" '
             f'height="{head_h + row_h * len(rows)}" fill="#ffffff" '
             f'stroke="#000000" stroke-width="4"/>')
    heads = ["물질명", "국제연합번호", "그림문자"]
    for ci, htxt in enumerate(heads):
        cx = col_x[ci] + col_w[ci] / 2
        p.append(f'<text x="{cx:.1f}" y="{table_y + head_h / 2:.1f}" '
                 f'font-family="{_FONT}" font-size="26" font-weight="700" '
                 f'fill="#000000" text-anchor="middle" '
                 f'dominant-baseline="central">{esc(htxt)}</text>')
    # 세로줄
    for ci in (1, 2):
        p.append(f'<line x1="{col_x[ci]}" y1="{table_y}" x2="{col_x[ci]}" '
                 f'y2="{total_h - 2}" stroke="#000000" stroke-width="2"/>')
    # 가로줄
    for ri in range(len(rows) + 1):
        y = table_y + head_h + row_h * ri
        if ri == len(rows):
            break
        p.append(f'<line x1="2" y1="{y:.1f}" x2="{B_MM-2}" y2="{y:.1f}" '
                 f'stroke="#000000" stroke-width="2"/>')

    for ri, ent in enumerate(rows):
        cy = table_y + head_h + row_h * ri + row_h / 2
        name = (ent.get("name") or "").strip()
        if name:
            fs_n = min(24.0, (col_w[0] - 24) / max(_text_units(name), 1))
            p.append(f'<text x="{col_w[0] / 2:.1f}" y="{cy:.1f}" '
                     f'font-family="{_FONT}" font-size="{fs_n:.1f}" '
                     f'fill="#000000" text-anchor="middle" '
                     f'dominant-baseline="central">{esc(name)}</text>')
        un = (ent.get("un") or "").strip()
        if un:
            p.append(f'<text x="{col_x[1] + col_w[1] / 2:.1f}" y="{cy:.1f}" '
                     f'font-family="{_FONT}" font-size="26" fill="#000000" '
                     f'text-anchor="middle" dominant-baseline="central">'
                     f'{esc(un)}</text>')
        pics = [c for c in dict.fromkeys(ent.get("pictograms") or [])
                if _pic_b64(c)][:6]
        if pics:
            size = min(56.0, (col_w[2] - 20 - 4 * (len(pics) - 1)) / len(pics))
            tot = size * len(pics) + 4 * (len(pics) - 1)
            x0 = col_x[2] + (col_w[2] - tot) / 2
            for k, code in enumerate(pics):
                p.append(f'<image x="{x0 + k * (size + 4):.1f}" '
                         f'y="{cy - size / 2:.1f}" width="{size:.1f}" '
                         f'height="{size:.1f}" '
                         f'href="data:image/png;base64,{_pic_b64(code)}"/>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{B_MM / 10}cm" height="{total_h / 10:.1f}cm" '
            f'viewBox="0 0 {B_MM} {total_h:.1f}">'
            f'<rect width="{B_MM}" height="{total_h:.1f}" fill="#ffffff"/>'
            + "".join(p) + "</svg>")
