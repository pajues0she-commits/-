# -*- coding: utf-8 -*-
"""MSDS PDF → 화학물질 작업공정별 관리 요령 엑셀 자동 작성 웹 앱.

실행:  streamlit run app.py
"""
import io
import re

import streamlit as st

from ghs_data import PICTOGRAM_NAMES
from msds_parser import MsdsData, parse_msds
from excel_writer import build_workbook
from preview import preview_html
from ncis_api import (BASE_URL as NCIS_BASE_URL, _contains as _ncis_contains,
                      extract_entry, parse_items, search_substance)
from sign_writer import KREACH_URL, build_sign_svg, parse_kreach_text

st.set_page_config(page_title="MSDS 자동 작성 도구", page_icon="🧪",
                   layout="wide")

st.title("🧪 MSDS 자동 작성 도구")
st.caption("「화학물질 작업공정별 관리요령」 메뉴에서 MSDS PDF를 업로드하면 항목을 자동 "
           "추출해 엑셀 양식을 만들고, 올린 물질은 「유해화학물질 규격표지」(화학물질관리법 "
           "시행규칙 별표 2) 메뉴에도 함께 반영됩니다.")

_PIC_OPTIONS = [f"{code} {name}" for code, name in PICTOGRAM_NAMES.items()]


def _pic_label(code: str) -> str:
    return f"{code} {PICTOGRAM_NAMES.get(code, '')}"


tab_manage, tab_sign = st.tabs(
    ["📋 화학물질 작업공정별 관리요령", "🚧 유해화학물질 규격표지"])

with tab_manage:
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
    with tab_manage, st.expander(
            f"📄 {name} — {data.product_name or '제품명 미확인'}",
            expanded=len(st.session_state.parsed) == 1):
        for w in data.warnings:
            st.warning(w)

        edit_col, prev_col = st.columns([1.1, 1], gap="medium")

        with edit_col:
            c1, c2 = st.columns([2, 1])
            product = c1.text_input("제품명 〔MSDS 1항 화학제품과 회사에 관한 정보〕",
                                    data.product_name, key=f"p_{name}",
                                    help="괄호로 주성분·농도를 덧붙일 수 있습니다. 예: TOC Base Solution (수산화나트륨 3.2%)")
            signal = c2.selectbox("신호어 〔MSDS 2항〕", ["위험", "경고", ""],
                                  index=["위험", "경고", ""].index(
                                      data.signal_word if data.signal_word in ("위험", "경고") else ""),
                                  format_func=lambda v: v or "해당없음",
                                  key=f"s_{name}")

            pics = st.multiselect("GHS 그림문자 〔MSDS 2항 유해성·위험성 — 경고표지 항목〕",
                                  _PIC_OPTIONS,
                                  default=[_pic_label(c) for c in data.pictograms
                                           if c in PICTOGRAM_NAMES],
                                  key=f"g_{name}")
            pic_codes = [p.split()[0] for p in pics]

            def area(label, items, key, height=110):
                return st.text_area(label, "\n".join(items), key=f"{key}_{name}",
                                    height=height,
                                    help="한 줄이 항목 하나가 되며 엑셀에는 '▶ '가 자동으로 붙습니다.")

            col_l, col_r = st.columns(2)
            with col_l:
                hazards = area("유해·위험문구 〔MSDS 2항 유해성·위험성〕", data.hazards, "hz")
                ppe = area("적절한 보호구 〔MSDS 8항 노출방지 및 개인보호구〕", data.ppe, "ppe")
                inhal = area("응급조치 — 흡입 시 〔MSDS 4항 응급조치 요령〕", data.inhalation, "in")
                ingest = area("응급조치 — 먹었을 때 〔MSDS 4항 응급조치 요령〕", data.ingestion, "ig")
            with col_r:
                precs = area("안전·보건상의 취급주의 사항 〔MSDS 2항 예방조치문구〕", data.precautions, "pr")
                skin = area("응급조치 — 피부·눈 접촉 시 〔MSDS 4항 응급조치 요령〕", data.skin_eye, "sk")
                emerg = area("응급대응 (소화제·화재·누출 대처) 〔MSDS 5항 폭발·화재시 / 6항 누출사고 시〕", data.emergency, "em")

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
            un_number=data.un_number,
        )
        records.append(rec)

        with prev_col:
            st.markdown("##### 🔍 미리보기 (엑셀 양식과 동일)")
            st.markdown(preview_html(rec), unsafe_allow_html=True)

with tab_manage:
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

with tab_sign:
    st.markdown("**화학물질관리법 시행규칙 [별표 2] 유해화학물질의 표시방법**(제12조제2항 관련) "
                "1호 — 보관·저장시설/진열·보관 장소 표지 시안을 만듭니다.  \n"
                "규격: a=50cm, b=(3/2)a=75cm, c=(1/4)a=12.5cm, d=(1/4)a=12.5cm · "
                "바탕 흰색 / 테두리 검정 / 유해화학물질 글자 빨강(높이 65% 이상) / "
                "관리책임자·비상전화 글자 검정")
    c1, c2, c3 = st.columns(3)
    manager = c1.text_input("관리책임자 (성명)", key="sign_mgr")
    phone = c2.text_input("비상전화", key="sign_ph1",
                          help="상시 연락이 가능한 전화번호를 기재해야 합니다.")
    phone2 = c3.text_input("연락처 (보조, 선택)", key="sign_ph2")

    if "manual_subs" not in st.session_state:
        st.session_state.manual_subs = []

    # 화학물질 추가 ① — NCIS(공공데이터포털) 자동 조회
    st.markdown("###### 화학물질 추가 ① — 물질명으로 NCIS 자동 조회")
    api_key = st.text_input(
        "공공데이터포털 API 인증키 (serviceKey)", type="password", key="ncis_key",
        help=f"{NCIS_BASE_URL} 서비스를 공공데이터포털(data.go.kr)에서 활용 신청 후 "
             "발급받은 인증키를 입력하세요.")
    s1, s2 = st.columns([3, 1])
    ncis_q = s1.text_input("화학물질명", key="ncis_q", placeholder="예: 황산, 톨루엔")
    if s2.button("🔎 자동 조회"):
        if not api_key.strip():
            st.session_state.ncis_results = []
            st.session_state.ncis_err = "API 인증키를 먼저 입력해 주세요."
        elif not ncis_q.strip():
            st.session_state.ncis_results = []
            st.session_state.ncis_err = "조회할 화학물질명을 입력해 주세요."
        else:
            with st.spinner("NCIS 조회 중..."):
                found, _url, err = search_substance(api_key, ncis_q)
            st.session_state.ncis_results = found
            st.session_state.ncis_err = err
    for i, ent in enumerate(st.session_state.get("ncis_results", [])):
        r1, r2 = st.columns([5, 1])
        r1.markdown(f"**{ent['name'] or '(이름 없음)'}**"
                    f"{' (CAS ' + ent['cas'] + ')' if ent.get('cas') else ''} — "
                    f"국제연합번호: {ent['un'] or '없음'} · "
                    f"그림문자: {', '.join(ent['pictograms']) or '없음'}")
        if r2.button("표에 추가", key=f"ncis_add_{i}"):
            st.session_state.manual_subs.append(
                {"name": ent["name"], "un": ent["un"],
                 "pictograms": ent["pictograms"]})
            st.session_state.ncis_results = []
            st.rerun()
    if st.session_state.get("ncis_err"):
        st.warning(st.session_state.ncis_err)

    # 화학물질 추가 ② — KREACH(화학물질정보처리시스템) 검색 활용
    st.markdown(f"###### 화학물질 추가 ② — [🔍 KREACH 분류·표시 검색 열기]({KREACH_URL})")
    st.caption("위 링크에서 물질을 검색한 뒤 결과·상세 화면 내용을 전체 선택(Ctrl+A)·"
               "복사(Ctrl+C)해서 아래에 붙여 넣으면 물질명·국제연합번호·그림문자"
               "(H코드 포함 시 자동 판정)를 인식해 표에 추가합니다.")
    with st.form("manual_add", clear_on_submit=True):
        a1, a2 = st.columns([2, 1])
        add_nm = a1.text_input("화학물질명")
        add_un = a2.text_input("국제연합번호(UN No.)")
        add_pics = st.multiselect("그림문자", _PIC_OPTIONS)
        add_paste = st.text_area("KREACH 검색 결과 붙여넣기 (선택 — 붙여 넣으면 자동 인식)",
                                 height=90)
        if st.form_submit_button("＋ 물질 추가"):
            ent = {"name": "", "un": "", "pictograms": []}
            pasted = add_paste.strip()
            if pasted:
                # NCIS API 응답(JSON/XML)을 붙여 넣은 경우 정확한 필드 파싱을 우선
                items, _api_err = parse_items(pasted)
                if items:
                    hits = [it for it in items
                            if not add_nm.strip() or _ncis_contains(it, add_nm)]
                    ent = extract_entry((hits or items)[0])
                    if len(hits or items) > 1:
                        st.info(f"API 응답에서 {len(hits or items)}건이 인식되어 "
                                "첫 번째 물질을 추가했습니다. 물질명을 함께 입력하면 "
                                "정확히 걸러집니다.")
                else:
                    ent = parse_kreach_text(pasted)
            ent["name"] = add_nm.strip() or ent["name"]
            ent["un"] = add_un.strip() or ent["un"]
            ent["pictograms"] = [p.split()[0] for p in add_pics] or ent["pictograms"]
            if ent["name"] or ent["un"] or ent["pictograms"]:
                st.session_state.manual_subs.append(
                    {"name": ent["name"], "un": ent["un"],
                     "pictograms": ent["pictograms"]})
            else:
                st.warning("물질 정보를 인식하지 못했습니다. 물질명을 입력해 주세요.")

    entries = []
    if records:
        st.markdown("###### MSDS에서 불러온 물질 〔국제연합번호: MSDS 14항 운송에 필요한 정보〕")
        for i, rec in enumerate(records):
            e1, e2 = st.columns([2, 1])
            nm = e1.text_input("물질명", rec.product_name,
                               key=f"sign_nm_{rec.source_name}")
            un = e2.text_input("국제연합번호(UN No.)", rec.un_number,
                               key=f"sign_un_{rec.source_name}")
            entries.append({"name": nm, "un": un, "pictograms": rec.pictograms})
    if st.session_state.manual_subs:
        st.markdown("###### 직접 추가한 물질")
        for i, ent in enumerate(list(st.session_state.manual_subs)):
            e1, e2 = st.columns([5, 1])
            e1.markdown(f"**{ent['name'] or '(물질명 미입력)'}** — "
                        f"국제연합번호: {ent['un'] or '없음'} · "
                        f"그림문자: {', '.join(ent['pictograms']) or '없음'}")
            if e2.button("삭제", key=f"sign_del_{i}"):
                st.session_state.manual_subs.pop(i)
                st.rerun()
        entries += st.session_state.manual_subs
    if not entries:
        st.info("MSDS PDF를 업로드하거나 위에서 물질을 직접 추가하면 표에 채워집니다.")

    svg = build_sign_svg(entries, manager, phone, phone2)
    st.download_button("⬇️ 표지판 시안 다운로드 (SVG, 실측 75×50cm+표)", svg,
                       file_name="유해화학물질_표지판.svg", mime="image/svg+xml")
    preview_svg = re.sub(r'width="[^"]+" height="[^"]+"', 'width="100%"',
                         svg, count=1)   # 화면에서는 폭에 맞춰 축소 표시
    st.markdown(
        f'<div style="border:1px solid #ccc;background:#fff;padding:10px;">'
        f'{preview_svg}</div>', unsafe_allow_html=True)
