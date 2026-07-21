# -*- coding: utf-8 -*-
"""MSDS PDF → 화학물질 작업공정별 관리 요령 엑셀 자동 작성 웹 앱.

실행:  streamlit run app.py
"""
import io
import os

import streamlit as st

from ghs_data import PICTOGRAM_NAMES
from msds_parser import MsdsData, parse_msds
from excel_writer import build_workbook, GHS_DIR

st.set_page_config(page_title="MSDS → 관리요령 엑셀 자동작성", page_icon="🧪",
                   layout="wide")

st.title("🧪 MSDS PDF → 화학물질 작업공정별 관리 요령")
st.caption("MSDS PDF를 업로드하면 항목을 자동 추출합니다. 내용을 확인·수정한 뒤 "
           "엑셀(양식 동일)로 다운로드하세요. 물질 여러 개를 올리면 시트가 하나씩 만들어집니다.")

_PIC_OPTIONS = [f"{code} {name}" for code, name in PICTOGRAM_NAMES.items()]


def _pic_label(code: str) -> str:
    return f"{code} {PICTOGRAM_NAMES.get(code, '')}"


uploaded = st.file_uploader("MSDS PDF 업로드 (여러 파일 가능)", type=["pdf"],
                            accept_multiple_files=True)

if "parsed" not in st.session_state:
    st.session_state.parsed = {}

# 새로 올라온 파일만 파싱 (수정 내용 보존)
current_names = [f.name for f in uploaded] if uploaded else []
for f in uploaded or []:
    if f.name not in st.session_state.parsed:
        with st.spinner(f"{f.name} 분석 중..."):
            try:
                data = parse_msds(io.BytesIO(f.getvalue()), source_name=f.name)
            except Exception as e:  # 손상된 PDF 등
                data = MsdsData(source_name=f.name,
                                warnings=[f"PDF를 읽지 못했습니다: {e}"])
        st.session_state.parsed[f.name] = data
for name in list(st.session_state.parsed):
    if name not in current_names:
        del st.session_state.parsed[name]

records = []
for name, data in st.session_state.parsed.items():
    with st.expander(f"📄 {name} — {data.product_name or '제품명 미확인'}",
                     expanded=len(st.session_state.parsed) == 1):
        for w in data.warnings:
            st.warning(w)

        c1, c2 = st.columns([2, 1])
        product = c1.text_input("제품명", data.product_name, key=f"p_{name}",
                                help="괄호로 주성분·농도를 덧붙일 수 있습니다. 예: TOC Base Solution (수산화나트륨 3.2%)")
        signal = c2.selectbox("신호어", ["위험", "경고", ""],
                              index=["위험", "경고", ""].index(
                                  data.signal_word if data.signal_word in ("위험", "경고") else ""),
                              key=f"s_{name}")

        pics = st.multiselect("GHS 그림문자", _PIC_OPTIONS,
                              default=[_pic_label(c) for c in data.pictograms
                                       if c in PICTOGRAM_NAMES],
                              key=f"g_{name}")
        pic_codes = [p.split()[0] for p in pics]
        if pic_codes:
            cols = st.columns(9)
            for i, code in enumerate(pic_codes[:9]):
                path = os.path.join(GHS_DIR, f"{code}.png")
                if os.path.exists(path):
                    cols[i].image(path, width=70, caption=code)

        def area(label, items, key, height=110):
            return st.text_area(label, "\n".join(items), key=f"{key}_{name}",
                                height=height,
                                help="한 줄이 항목 하나가 되며 엑셀에는 '▶ '가 자동으로 붙습니다.")

        col_l, col_r = st.columns(2)
        with col_l:
            hazards = area("유해·위험문구 (건강·환경 유해성, 물리적 위험성)", data.hazards, "hz")
            ppe = area("적절한 보호구", data.ppe, "ppe")
            inhal = area("응급조치 — 흡입 시", data.inhalation, "in")
            ingest = area("응급조치 — 먹었을 때", data.ingestion, "ig")
        with col_r:
            precs = area("안전·보건상의 취급주의 사항", data.precautions, "pr")
            skin = area("응급조치 — 피부·눈 접촉 시", data.skin_eye, "sk")
            emerg = area("응급대응 (소화제·화재·누출 대처)", data.emergency, "em")

        rec = MsdsData(
            source_name=name,
            product_name=product.strip(),
            signal_word=signal,
            pictograms=pic_codes,
            hazards=[l.strip() for l in hazards.splitlines() if l.strip()],
            precautions=[l.strip() for l in precs.splitlines() if l.strip()],
            ppe=[l.strip() for l in ppe.splitlines() if l.strip()],
            inhalation=[l.strip() for l in inhal.splitlines() if l.strip()],
            skin_eye=[l.strip() for l in skin.splitlines() if l.strip()],
            ingestion=[l.strip() for l in ingest.splitlines() if l.strip()],
            emergency=[l.strip() for l in emerg.splitlines() if l.strip()],
        )
        records.append(rec)

if records:
    st.divider()
    if st.button("📥 엑셀 파일 생성", type="primary"):
        try:
            xlsx = build_workbook(records)
            st.session_state.xlsx = xlsx
        except Exception as e:
            st.error(f"엑셀 생성 실패: {e}")
    if st.session_state.get("xlsx"):
        st.download_button(
            "⬇️ 화학물질_작업공정별_관리요령.xlsx 다운로드",
            st.session_state.xlsx,
            file_name="화학물질_작업공정별_관리요령.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("MSDS PDF 파일을 업로드하면 여기에서 추출 결과를 확인하고 수정할 수 있습니다.")
