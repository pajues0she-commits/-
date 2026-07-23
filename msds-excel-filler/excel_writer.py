# -*- coding: utf-8 -*-
"""파싱된 MSDS 데이터를 '화학물질 작업공정별 관리 요령' 엑셀 양식에 기록한다.

assets/template.xlsx 는 업로드된 원본 양식에서 값만 비운 시트 1장짜리 파일이며,
물질마다 이 시트를 복제하여 채운다. 서식(병합·글꼴·테두리·행높이)은 그대로 유지된다.
"""
import io
import math
import os
import re

import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.properties import PageSetupProperties

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "template.xlsx")
GHS_DIR = os.path.join(ASSETS_DIR, "ghs")

# 원본 양식의 그림문자 크기: 1000125 EMU ≈ 105 px
_PIC_SIZE = 105
_PIC_ANCHORS_3 = ["D7", "F7", "H7"]           # 그림 1~3개일 때 (원본과 동일 배치)
_PIC_ANCHORS_6 = ["D7", "E7", "F7", "G7", "H7", "I7"]  # 4개 이상이면 축소 배치

# 양식 셀 좌표
_CELLS = {
    "product": "A10", "signal": "J10",
    "hazard_l": "A15", "hazard_r": "F15",
    "prec_l": "A17", "prec_r": "F17",
    "ppe": "A19",
    "inhalation": "A22", "skin_eye": "F22",
    "ingestion": "A30", "emergency": "F30",
}


def _bullets(items) -> str:
    return "\n".join("▶ " + s for s in items if s.strip())


# ── 행 높이 자동 조절 ────────────────────────────────────────────────────
# 내용이 길면 셀이 가려지므로 필요한 줄 수를 추정해 블록의 마지막 행을
# 늘린다. 인쇄는 fitToPage(가로·세로 1페이지)로 잡아 두므로 행이 늘어나도
# 시트(탭)마다 항상 A4 한 장에 맞춰 출력된다.
_LINE_PT = 14.2          # 10.5pt 글꼴의 줄 높이(pt)
_BLOCK_PAD = 6           # 블록 위아래 여유(pt)
# (블록 행 범위, 반쪽 너비(문자단위)) — 반쪽 블록 ≈ 40, 전체 너비 ≈ 82
_HALF_CAP, _FULL_CAP = 44, 90
_BLOCKS = [
    # (rows, capacity, 채우는 값 키 목록 — 좌/우 중 더 긴 쪽 기준)
    ((15, 15), _HALF_CAP, ("hazard_l", "hazard_r")),
    ((17, 17), _HALF_CAP, ("prec_l", "prec_r")),
    ((19, 19), _FULL_CAP, ("ppe",)),
    ((22, 28), _HALF_CAP, ("inhalation", "skin_eye")),
    ((30, 36), _HALF_CAP, ("ingestion", "emergency")),
]


def _text_lines(text: str, cap_units: float) -> int:
    """줄바꿈(wrap) 후 표시되는 줄 수를 추정한다. 한글은 2문자폭으로 계산."""
    total = 0
    for line in text.split("\n"):
        w = sum(1.9 if ord(ch) > 0x2E80 else 1.0 for ch in line)
        total += max(1, math.ceil(w / cap_units))
    return total


def _autofit_rows(ws, values: dict):
    for (r0, r1), cap, keys in _BLOCKS:
        texts = [values.get(k, "") for k in keys]
        lines = max((_text_lines(t, cap) for t in texts if t), default=0)
        if not lines:
            continue
        needed = lines * _LINE_PT + _BLOCK_PAD
        rows = list(range(r0, r1 + 1))
        current = sum(ws.row_dimensions[r].height or 16.5 for r in rows)
        if needed > current:
            last = ws.row_dimensions[rows[-1]]
            last.height = (last.height or 16.5) + (needed - current)


def _page_fit(ws):
    """탭마다 A4 세로 한 장에 맞춰 인쇄되도록 강제한다."""
    ws.print_area = "A1:J37"
    ws.page_setup.paperSize = 9          # A4
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.scale = None
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


def split_two(items):
    """항목을 좌/우 칸으로 절반씩 나눈다 (원본 양식이 두 칸 구성이므로)."""
    if len(items) <= 1:
        return items, []
    half = (len(items) + 1) // 2
    return items[:half], items[half:]


def _sheet_title(name: str, used: set) -> str:
    title = re.sub(r"[\\/*?\[\]:]", " ", name).strip() or "MSDS"
    title = title[:31]
    base, n = title, 2
    while title in used:
        suffix = f" ({n})"
        title = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(title)
    return title


def fill_sheet(ws, data):
    """복제된 양식 시트 1장에 MsdsData를 기록한다."""
    values = {"product": data.product_name or "", "signal": data.signal_word or ""}
    left, right = split_two(data.hazards)
    values["hazard_l"], values["hazard_r"] = _bullets(left), _bullets(right)
    left, right = split_two(data.precautions)
    values["prec_l"], values["prec_r"] = _bullets(left), _bullets(right)
    values["ppe"] = _bullets(data.ppe)
    values["inhalation"] = _bullets(data.inhalation)
    values["skin_eye"] = _bullets(data.skin_eye)
    values["ingestion"] = _bullets(data.ingestion)
    values["emergency"] = _bullets(data.emergency)
    for key, addr in _CELLS.items():
        ws[addr] = values[key]

    _autofit_rows(ws, values)
    _page_fit(ws)

    pics = list(dict.fromkeys(data.pictograms))[:6]
    anchors = _PIC_ANCHORS_3 if len(pics) <= 3 else _PIC_ANCHORS_6
    size = _PIC_SIZE if len(pics) <= 3 else 68
    for code, anchor in zip(pics, anchors):
        path = os.path.join(GHS_DIR, f"{code}.png")
        if not os.path.exists(path):
            continue
        img = XLImage(path)
        img.width = img.height = size
        ws.add_image(img, anchor)


def build_workbook(records, template_path: str = TEMPLATE_PATH) -> bytes:
    """MsdsData 목록으로 완성된 통합 문서(xlsx bytes)를 만든다."""
    if not records:
        raise ValueError("기록할 MSDS 데이터가 없습니다.")
    wb = openpyxl.load_workbook(template_path)
    template = wb["Template"]
    used = set()
    for data in records:
        ws = wb.copy_worksheet(template)
        ws.title = _sheet_title(data.product_name or data.source_name, used)
        fill_sheet(ws, data)
    wb.remove(template)
    wb.active = 0
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
