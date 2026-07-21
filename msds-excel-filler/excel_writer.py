# -*- coding: utf-8 -*-
"""파싱된 MSDS 데이터를 '화학물질 작업공정별 관리 요령' 엑셀 양식에 기록한다.

assets/template.xlsx 는 업로드된 원본 양식에서 값만 비운 시트 1장짜리 파일이며,
물질마다 이 시트를 복제하여 채운다. 서식(병합·글꼴·테두리·행높이)은 그대로 유지된다.
"""
import io
import os
import re

import openpyxl
from openpyxl.drawing.image import Image as XLImage

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


def _split_two(items):
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
    ws[_CELLS["product"]] = data.product_name or ""
    ws[_CELLS["signal"]] = data.signal_word or ""

    left, right = _split_two(data.hazards)
    ws[_CELLS["hazard_l"]] = _bullets(left)
    ws[_CELLS["hazard_r"]] = _bullets(right)

    left, right = _split_two(data.precautions)
    ws[_CELLS["prec_l"]] = _bullets(left)
    ws[_CELLS["prec_r"]] = _bullets(right)

    ws[_CELLS["ppe"]] = _bullets(data.ppe)
    ws[_CELLS["inhalation"]] = _bullets(data.inhalation)
    ws[_CELLS["skin_eye"]] = _bullets(data.skin_eye)
    ws[_CELLS["ingestion"]] = _bullets(data.ingestion)
    ws[_CELLS["emergency"]] = _bullets(data.emergency)

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
