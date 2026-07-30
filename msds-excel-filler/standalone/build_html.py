# -*- coding: utf-8 -*-
"""단일 HTML 파일(standalone/MSDS_관리요령_작성기.html) 빌드 스크립트.

src/app.html 의 자리표시자에 라이브러리(vendor/), 빈 양식(시트 20장),
GHS 그림문자, H-code 문구 테이블을 채워 완전한 오프라인 단일 파일을 만든다.

실행:  python build_html.py
"""
import base64
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from chem_db import CHEM_DB  # noqa: E402
from ghs_data import H_STATEMENTS  # noqa: E402
from review_logic import CRITERIA_REGISTER, CRITERIA_REVIEW  # noqa: E402
import ko_spacing  # noqa: E402
import risk_logic  # noqa: E402

VENDOR = os.path.join(HERE, "vendor")
OUT = os.path.join(HERE, "켐세이프_화학물질통합안전관리.html")
FORM_SHEETS = 20  # 한 파일에서 처리 가능한 최대 물질 수


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def js_inline(path):
    """<script> 안에 안전하게 넣을 수 있도록 스크립트 종료 태그를 이스케이프."""
    return read(path).replace("</script", "<\\/script")


def build_template20() -> bytes:
    """assets/template.xlsx(1장)를 복제해 빈 양식 20장짜리 통합 문서를 만든다."""
    import openpyxl
    wb = openpyxl.load_workbook(os.path.join(ROOT, "assets", "template.xlsx"))
    tpl = wb["Template"]
    for i in range(FORM_SHEETS - 1):
        ws = wb.copy_worksheet(tpl)
        ws.title = f"Form{i + 2}"
    tpl.title = "Form1"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main():
    html = read(os.path.join(HERE, "src", "app.html"))

    libs = {
        "/*__PDFJS_WORKER__*/": js_inline(os.path.join(VENDOR, "pdf.worker.min.js")),
        "/*__PDFJS__*/": js_inline(os.path.join(VENDOR, "pdf.min.js")),
        "/*__EXCELJS__*/": js_inline(os.path.join(VENDOR, "exceljs.min.js")),
        "/*__JSZIP__*/": js_inline(os.path.join(VENDOR, "jszip.min.js")),
    }
    for marker, code in libs.items():
        if marker not in html:
            raise SystemExit(f"자리표시자 없음: {marker}")
        html = html.replace(marker, code)

    html = html.replace("__TEMPLATE_B64__",
                        base64.b64encode(build_template20()).decode())

    ghs = {}
    ghs_dir = os.path.join(ROOT, "assets", "ghs")
    for name in sorted(os.listdir(ghs_dir)):
        if name.endswith(".png"):
            with open(os.path.join(ghs_dir, name), "rb") as f:
                ghs[name[:-4]] = base64.b64encode(f.read()).decode()
    html = html.replace("__GHS_B64_JSON__", json.dumps(ghs))

    cmaps = {}
    cmap_dir = os.path.join(VENDOR, "cmaps")
    for name in sorted(os.listdir(cmap_dir)):
        if name.endswith(".bcmap"):
            with open(os.path.join(cmap_dir, name), "rb") as f:
                cmaps[name[:-6]] = base64.b64encode(f.read()).decode()
    html = html.replace("__CMAPS_B64_JSON__", json.dumps(cmaps))
    html = html.replace("__H_STATEMENTS_JSON__",
                        json.dumps(H_STATEMENTS, ensure_ascii=False))
    html = html.replace("__CHEM_DB_JSON__", json.dumps([
        {"name": e["name"], "alias": e["alias"], "cas": e["cas"],
         "un": e["un"], "pics": e["pics"]} for e in CHEM_DB],
        ensure_ascii=False))
    html = html.replace("__REVIEW_CRITERIA_JSON__", json.dumps(
        {"review": CRITERIA_REVIEW, "register": CRITERIA_REGISTER},
        ensure_ascii=False))
    # 화학물질 위험성평가 — 기준 데이터·엑셀 양식 원본 (risk_logic.py)
    html = html.replace("__RISK_DATA_JSON__", json.dumps({
        "db": risk_logic.RISK_DB,
        "possFreq": risk_logic.POSS_FREQ,
        "possAmount": risk_logic.POSS_AMOUNT,
        "env": risk_logic._ENV,
        "waterReact": risk_logic.WATER_REACT_OPTIONS,
        "decomp": risk_logic.DECOMP_OPTIONS,
        "iarc": risk_logic.IARC_OPTIONS,
        "pbt": risk_logic.PBT_OPTIONS,
        "fields": risk_logic.RISK_FIELDS,
        "groups": risk_logic.RISK_GROUPS,
        "autoCodes": risk_logic.AUTO_CODES,
        "autoLabels": risk_logic.AUTO_LABELS,
        "sheets": risk_logic.SHEETS,
        "tiers": risk_logic.TIERS,
        "criteria": risk_logic.OVERALL_CRITERIA,
    }, ensure_ascii=False))
    with open(os.path.join(ROOT, "assets", "risk_template.xlsx"), "rb") as f:
        html = html.replace("__RISK_TPL_B64__",
                            base64.b64encode(f.read()).decode())
    with open(os.path.join(ROOT, "assets", "ci.png"), "rb") as f:
        html = html.replace("__CI_B64__",
                            base64.b64encode(f.read()).decode())
    html = html.replace("__KO_DICT_JSON__", json.dumps({
        "nouns": ko_spacing.NOUNS,
        "funcs": ko_spacing.FUNCS,
        "aux": sorted(ko_spacing.AUX_ATTACH),
        "particles": ko_spacing.PARTICLES,
    }, ensure_ascii=False))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"완료: {OUT} ({os.path.getsize(OUT) / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
