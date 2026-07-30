# -*- coding: utf-8 -*-
"""MSDS PDF → 화학물질 작업공정별 관리 요령 엑셀 자동 작성 웹 앱.

실행:  streamlit run app.py
"""
import io
import json
import os
import re

import streamlit as st

from ghs_data import PICTOGRAM_NAMES
from msds_parser import MsdsData, parse_msds
from excel_writer import build_workbook
from preview import preview_html
from chem_db import CHEM_DB, search_chem
from sign_writer import build_sign_svg
from review_logic import (CRITERIA_REVIEW, CRITERIA_REGISTER, assess,
                          components_text)
import risk_logic as RL

st.set_page_config(page_title="MSDS 자동 작성 도구", page_icon="🧪",
                   layout="wide")

st.title("🧪 MSDS 자동 작성 도구")
st.caption("「화학물질 작업공정별 관리요령」 메뉴에서 MSDS PDF를 업로드하면 항목을 자동 "
           "추출해 엑셀 양식을 만들고, 「화학물질 도입검토」 메뉴에서는 MSDS에서 물질명·"
           "제조사·주요성분을 자동 인식해 도입검토·정보등록 대상 여부를 판독하고 누적 "
           "관리하며, 「유해화학물질 규격표지」 메뉴에서는 화학물질명만 입력하면 CAS 번호·"
           "국제연합번호·그림문자가 자동 입력된 표지판 시안(화학물질관리법 시행규칙 "
           "별표 2)을 만듭니다.")

_PIC_OPTIONS = [f"{code} {name}" for code, name in PICTOGRAM_NAMES.items()]


def _pic_label(code: str) -> str:
    return f"{code} {PICTOGRAM_NAMES.get(code, '')}"


# 메뉴 — 라디오 내비게이션 (도입검토 → 위험성평가 버튼으로 이동할 수 있도록
# st.tabs 대신 사용: 프로그램에서 st.session_state.menu 변경으로 전환 가능)
_MENUS = ["📋 화학물질 작업공정별 관리요령", "🔍 화학물질 도입검토",
          "🧪 화학물질 위험성평가", "🚧 유해화학물질 규격표지"]
if "menu" not in st.session_state:
    st.session_state.menu = _MENUS[0]
if st.session_state.get("menu_jump"):     # 버튼으로 메뉴 이동 (다음 실행에 반영)
    st.session_state.menu = st.session_state.pop("menu_jump")
menu = st.radio("메뉴", _MENUS, horizontal=True, key="menu",
                label_visibility="collapsed")
st.markdown("<hr style='margin:0.2rem 0 1rem 0;'>", unsafe_allow_html=True)

uploaded = None
if menu == _MENUS[0]:
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
if menu == _MENUS[0]:
    for name in list(st.session_state.parsed):
        if name not in current_names:
            del st.session_state.parsed[name]

records = []
for name, data in (st.session_state.parsed.items()
                   if menu == _MENUS[0] else []):
    with st.expander(
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

if menu == _MENUS[0]:
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

# ── 화학물질 도입검토 ────────────────────────────────────────────────────
_REVIEW_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "review_db.json")


def _load_review_db():
    try:
        with open(_REVIEW_DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
            return db if isinstance(db, list) else []
    except Exception:
        return []


def _save_review_db(db):
    with open(_REVIEW_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)


def _review_xlsx(db, upload_rows) -> bytes:
    """도입검토 등록 목록(+현재 업로드 비교표)을 엑셀로 만든다."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    thin = Border(*[Side(style="thin")] * 4)
    head_fill = PatternFill("solid", fgColor="DDEBF7")
    head_font = Font(bold=True)
    # 대상 셀 컬러마킹: 도입검토 대상 = 노랑, 정보등록 대상 = 초록
    mark = {"도입검토 대상": PatternFill("solid", fgColor="FFEB9C"),
            "정보등록 대상": PatternFill("solid", fgColor="C6EFCE")}

    def fill_sheet(ws, headers, rows, widths):
        ws.append(headers)
        for c in ws[1]:
            c.fill, c.font, c.border = head_fill, head_font, thin
            c.alignment = Alignment(horizontal="center", vertical="center")
        for row in rows:
            ws.append(row)
        for r in ws.iter_rows(min_row=2):
            for c in r:
                c.border = thin
                c.alignment = Alignment(vertical="center", wrap_text=True)
                if c.value in mark:
                    c.fill = mark[c.value]
                    c.font = Font(bold=True)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "등록 목록"
    fill_sheet(ws,
               ["No.", "작성일", "화학물질명", "제조사", "MSDS 개정일자",
                "주요성분 및 함량", "도입검토", "정보등록", "MSDS 파일"],
               [[r.get("id"), r.get("date", ""), r.get("name", ""),
                 r.get("manufacturer", ""), r.get("revision", ""),
                 components_text(r.get("components", [])),
                 r.get("review", ""), r.get("register", ""),
                 r.get("source", "")] for r in db],
               [6, 12, 30, 22, 14, 50, 16, 16, 30])
    if upload_rows:
        ws2 = wb.create_sheet("업로드 비교표")
        fill_sheet(ws2,
                   ["파일", "화학물질명", "제조사", "MSDS 개정일자",
                    "주요성분 및 함량", "작성일", "도입검토", "정보등록"],
                   [[r["파일"], r["화학물질명"], r["제조사"],
                     r.get("MSDS 개정일자", ""), r["주요성분 및 함량"],
                     r["작성일"], r["도입검토"], r["정보등록"]]
                    for r in upload_rows],
                   [30, 30, 22, 14, 50, 12, 16, 16])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


if menu == _MENUS[1]:
    st.markdown("MSDS를 등록하면 **화학물질명·제조사·주요성분 및 함량**을 자동 인식해 "
                "비교표를 만들고, 기존 등록 이력과 비교해 **도입검토 대상·정보등록 대상** "
                "여부를 자동 판독합니다. 등록된 정보는 누적 관리되며, 같은 물질의 이전 "
                "MSDS와 비교할 수 있습니다.")
    with st.expander("ℹ️ 도입검토 대상·정보등록 대상 기준 보기"):
        st.markdown("**도입검토 대상**")
        for i, c in enumerate(CRITERIA_REVIEW, 1):
            st.markdown(f"{i}) {c}")
        st.markdown("**정보등록 대상**")
        for i, c in enumerate(CRITERIA_REGISTER, 1):
            st.markdown(f"{i}) {c}")
        st.caption("자동 판독은 이 프로그램에 등록된 이력과의 비교(물질명·구성성분) "
                   "결과이며 참고용입니다. 최종 판단은 사내 절차에 따라 확인하세요.")

    rv_uploaded = st.file_uploader("MSDS PDF 업로드 (여러 파일 가능)",
                                   type=["pdf"], accept_multiple_files=True,
                                   key="review_upload")

    if "review_parsed" not in st.session_state:
        st.session_state.review_parsed = {}
    for f in rv_uploaded or []:
        if f.name not in st.session_state.review_parsed:
            with st.spinner(f"{f.name} 분석 중..."):
                try:
                    d = parse_msds(io.BytesIO(f.getvalue()), source_name=f.name)
                except Exception as e:
                    d = MsdsData(source_name=f.name,
                                 warnings=[f"PDF를 읽지 못했습니다: {e}"])
            st.session_state.review_parsed[f.name] = d
    if rv_uploaded:                     # 업로더에서 뺀 파일만 카드 정리
        rv_names = [f.name for f in rv_uploaded]
        for n in list(st.session_state.review_parsed):
            if n not in rv_names:
                del st.session_state.review_parsed[n]

    # 일괄 작업 — 작성일 일괄 입력·일괄 등록 (업로드한 모든 MSDS 대상)
    bulk_save = False
    if st.session_state.review_parsed:
        b1, b2, b3 = st.columns([1, 1.6, 1.2])
        bulk_dt = b1.date_input("작성일 일괄 입력", value=None,
                                key="rv_bulk_dt", format="YYYY-MM-DD")
        b2.markdown("<div style='height:1.75em'></div>",
                    unsafe_allow_html=True)
        b3.markdown("<div style='height:1.75em'></div>",
                    unsafe_allow_html=True)
        if b2.button("📅 업로드한 모든 MSDS에 작성일 적용", key="rv_bulk_btn"):
            if bulk_dt is None:
                st.warning("일괄 적용할 작성일을 먼저 선택해 주세요.")
            else:
                for n in st.session_state.review_parsed:
                    st.session_state[f"rv_dt_{n}"] = bulk_dt
        bulk_save = b3.button("💾 모든 MSDS 일괄 등록", key="rv_bulk_save")

    review_db = _load_review_db()
    rv_rows = []
    bulk_saved, bulk_skipped = [], []
    for name, data in st.session_state.review_parsed.items():
        with st.expander(f"📄 {name} — {data.product_name or '제품명 미확인'}",
                         expanded=len(st.session_state.review_parsed) == 1):
            c1, c2, c3, c4 = st.columns([1.5, 1.2, 0.9, 0.9])
            rv_nm = c1.text_input("화학물질명", data.product_name,
                                  key=f"rv_nm_{name}")
            rv_mf = c2.text_input("제조사", data.manufacturer,
                                  key=f"rv_mf_{name}")
            rv_rev = c3.text_input("MSDS 개정일자", data.revision_date,
                                   key=f"rv_rev_{name}",
                                   placeholder="YYYY-MM-DD",
                                   help="MSDS의 최종 개정일자 — 개정일자가 "
                                        "변경되면 정보등록 대상입니다.")
            rv_dt = c4.date_input("작성일 (직접 입력)", value=None,
                                  key=f"rv_dt_{name}", format="YYYY-MM-DD",
                                  help="연도부터 날짜까지 작성자가 직접 입력합니다.")
            if not data.components:
                st.warning("구성성분(3항)을 자동 인식하지 못했습니다. "
                           "아래 표에 직접 입력해 주세요.")
            st.markdown("**주요성분 및 함량** 〔MSDS 3항 구성성분의 명칭 및 함유량〕")
            comp_rows = st.data_editor(
                [{"성분명": c["name"], "CAS 번호": c["cas"],
                  "함유량": c["content"]} for c in data.components] or
                [{"성분명": "", "CAS 번호": "", "함유량": ""}],
                num_rows="dynamic", key=f"rv_comp_{name}",
                use_container_width=True)
            comps = [{"name": (r.get("성분명") or "").strip(),
                      "cas": (r.get("CAS 번호") or "").strip(),
                      "content": (r.get("함유량") or "").strip()}
                     for r in comp_rows
                     if (r.get("성분명") or r.get("CAS 번호") or
                         r.get("함유량") or "").strip()]
            consumer = st.checkbox(
                "일반 소매점에서 일반 소비자 대상으로 판매되는 물질 (정보등록 제외)",
                key=f"rv_cons_{name}")

            res = assess(rv_nm, comps, review_db, consumer,
                         manufacturer=rv_mf, revision_date=rv_rev)
            (st.warning if res["review"] else st.success)(
                f"**{res['review_label']}** — {res['review_reason']}")
            (st.info if res["register"] else st.success)(
                f"**{res['register_label']}** — {res['register_reason']}")
            if res["review"]:
                # 도입검토 대상 → 「위험성 평가」 버튼으로 위험성평가 메뉴 이동
                if st.button("🧪 위험성 평가 — 이 MSDS로 작성",
                             key=f"rv_risk_{name}",
                             help="도입검토 대상 물질은 위험성평가를 진행합니다. "
                                  "이 MSDS의 인식 결과를 가지고 「화학물질 "
                                  "위험성평가」 메뉴로 이동합니다."):
                    st.session_state.risk_nonce = \
                        st.session_state.get("risk_nonce", 0) + 1
                    st.session_state.risk_src = {
                        "name": rv_nm.strip(), "manufacturer": rv_mf.strip(),
                        "revision": rv_rev.strip(), "components": comps,
                        "hcodes": data.hcodes, "vals": dict(data.risk),
                        "source": name}
                    st.session_state.menu_jump = _MENUS[2]
                    st.rerun()

            prior = res["same_name"] or res["same_comp"]
            if prior:
                last = prior[-1]
                st.markdown(f"###### 🔁 이전 등록과 비교 — {last.get('name')} "
                            f"(작성일 {last.get('date') or '미상'}, "
                            f"제조사 {last.get('manufacturer') or '미상'})")
                old = {(c.get("cas") or c.get("name")): c
                       for c in last.get("components", [])}
                new = {(c.get("cas") or c.get("name")): c for c in comps}
                diff_rows = []
                for k in list(old) + [k for k in new if k not in old]:
                    o, n2 = old.get(k), new.get(k)
                    diff_rows.append({
                        "성분명": (n2 or o).get("name") or "",
                        "CAS 번호": (n2 or o).get("cas") or "",
                        "이전 함유량": o.get("content") if o else "(없던 성분)",
                        "이번 함유량": n2.get("content") if n2 else "(빠진 성분)",
                        "변경": "동일" if (o and n2 and
                                        (o.get("content") or "").replace(" ", "")
                                        == (n2.get("content") or "").replace(" ", ""))
                                else "변경",
                    })
                st.dataframe(diff_rows, use_container_width=True,
                             hide_index=True)

            if st.button("💾 등록 (누적 관리 목록에 저장)", type="primary",
                         key=f"rv_save_{name}") or bulk_save:
                if rv_dt is None:
                    st.error("작성일을 입력한 뒤 등록해 주세요.")
                    bulk_skipped.append(name)
                elif not rv_nm.strip():
                    st.error("화학물질명을 입력한 뒤 등록해 주세요.")
                    bulk_skipped.append(name)
                else:
                    review_db.append({
                        "id": max([r.get("id", 0) for r in review_db] or [0]) + 1,
                        "date": str(rv_dt), "name": rv_nm.strip(),
                        "manufacturer": rv_mf.strip(),
                        "revision": rv_rev.strip(), "components": comps,
                        "source": name,
                        "review": res["review_label"],
                        "register": res["register_label"]})
                    _save_review_db(review_db)
                    bulk_saved.append(name)
                    st.success(f"「{rv_nm.strip()}」을(를) 등록했습니다. "
                               f"(누적 {len(review_db)}건)")

            rv_rows.append({"파일": name, "화학물질명": rv_nm, "제조사": rv_mf,
                            "MSDS 개정일자": rv_rev,
                            "주요성분 및 함량": components_text(comps),
                            "작성일": str(rv_dt) if rv_dt else "",
                            "도입검토": res["review_label"],
                            "정보등록": res["register_label"]})

    if bulk_save:
        if bulk_saved:
            st.success(f"일괄 등록 완료 — {len(bulk_saved)}건을 저장했습니다."
                       + (f" ({len(bulk_skipped)}건은 작성일·화학물질명이 없어 "
                          "건너뛰었습니다.)" if bulk_skipped else ""))
        elif bulk_skipped:
            st.warning("일괄 등록할 수 있는 항목이 없습니다 — 작성일과 "
                       "화학물질명을 먼저 입력해 주세요.")

    if rv_rows:
        st.markdown("##### 📊 비교표 — 업로드한 MSDS")
        st.dataframe(rv_rows, use_container_width=True, hide_index=True)
    else:
        st.info("MSDS PDF 파일을 업로드하면 화학물질명·제조사·주요성분 및 함량을 "
                "자동 인식해 비교표를 만들고 대상 여부를 판독합니다.")

    st.divider()
    st.markdown("##### 🗂 등록된 화학물질 조회 (누적 관리)")
    f1, f2, f3 = st.columns([2, 1, 1])
    rv_q = f1.text_input("물질명·제조사·CAS 번호로 검색", key="rv_q",
                         placeholder="예: TOC BASE, 새론, 1310-73-2")
    rv_from = f2.date_input("작성일 시작 (기간별 조회)", value=None,
                            key="rv_from", format="YYYY-MM-DD")
    rv_to = f3.date_input("작성일 종료 (기간별 조회)", value=None,
                          key="rv_to", format="YYYY-MM-DD")
    q = rv_q.strip().lower()

    def _hit(r):
        d = r.get("date", "")
        if rv_from and (not d or d < str(rv_from)):
            return False
        if rv_to and (not d or d > str(rv_to)):
            return False
        if not q:
            return True
        blob = " ".join([r.get("name", ""), r.get("manufacturer", ""),
                         components_text(r.get("components", []))]).lower()
        return q in blob
    shown = [r for r in review_db if _hit(r)]
    if shown:
        st.dataframe(
            [{"No.": r.get("id"), "작성일": r.get("date", ""),
              "화학물질명": r.get("name", ""),
              "제조사": r.get("manufacturer", ""),
              "MSDS 개정일자": r.get("revision", ""),
              "주요성분 및 함량": components_text(r.get("components", [])),
              "도입검토": r.get("review", ""), "정보등록": r.get("register", ""),
              "MSDS 파일": r.get("source", "")} for r in shown],
            use_container_width=True, hide_index=True)
        d1, d2, d3 = st.columns([1, 1.6, 1.6])
        del_id = d1.selectbox("삭제할 등록 번호(No.)", [r.get("id") for r in shown],
                              key="rv_del_sel")
        if d2.button("🗑️ 선택한 등록 삭제", key="rv_del_btn"):
            _save_review_db([r for r in review_db if r.get("id") != del_id])
            st.rerun()
        if d3.button(f"🗑️ 표시된 {len(shown)}건 일괄 삭제", key="rv_del_all"):
            ids = {r.get("id") for r in shown}
            _save_review_db([r for r in review_db if r.get("id") not in ids])
            st.rerun()
    else:
        st.caption("등록된 화학물질이 없습니다."
                   if not (q or rv_from or rv_to) else "검색 결과가 없습니다.")
    if review_db or rv_rows:
        st.download_button(
            "⬇️ 엑셀로 내보내기 (등록 목록 + 업로드 비교표)",
            _review_xlsx(review_db, rv_rows),
            file_name="화학물질_도입검토.xlsx",
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet")

# ── 화학물질 위험성평가 ─────────────────────────────────────────────────
_RISK_TPL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "assets", "risk_template.xlsx")

if menu == _MENUS[2]:
    st.markdown("도입검토 대상 화학물질의 **위험성평가**(물리화학적 · 환경오염 · "
                "작업자 안전보건, 유해성×가능성)를 작성합니다. MSDS에서 자동 "
                "인식한 값(H-Code·물리화학 특성·독성·환경 데이터)이 미리 채워지며, "
                "자동 인식되지 않은 항목은 직접 입력합니다. 완성된 평가는 "
                "**위험성평가 엑셀 양식**으로 내려받을 수 있습니다(양식 수식·서식 "
                "그대로 유지).")

    rk_up = st.file_uploader("MSDS PDF 업로드 (위험성평가 대상 물질)",
                             type=["pdf"], accept_multiple_files=False,
                             key="risk_upload",
                             help="「화학물질 도입검토」에서 판독한 MSDS는 카드의 "
                                  "「위험성평가 작성」 버튼으로 바로 가져올 수 "
                                  "있습니다.")
    if rk_up is not None and \
            st.session_state.get("risk_up_done") != rk_up.name:
        with st.spinner(f"{rk_up.name} 분석 중..."):
            try:
                d = parse_msds(io.BytesIO(rk_up.getvalue()),
                               source_name=rk_up.name)
                st.session_state.risk_nonce = \
                    st.session_state.get("risk_nonce", 0) + 1
                st.session_state.risk_src = {
                    "name": d.product_name, "manufacturer": d.manufacturer,
                    "revision": d.revision_date, "components": d.components,
                    "hcodes": d.hcodes, "vals": dict(d.risk),
                    "source": rk_up.name}
                st.session_state.risk_up_done = rk_up.name
            except Exception as e:
                st.error(f"PDF를 읽지 못했습니다: {e}")

    src = st.session_state.get("risk_src")
    if not src:
        st.info("MSDS를 업로드하거나, 「화학물질 도입검토」 메뉴에서 도입검토 "
                "대상으로 판정된 카드의 「🧪 화학물질 위험성평가 작성」 버튼으로 "
                "시작하세요.")
    else:
        n = st.session_state.get("risk_nonce", 0)

        def _k(name):
            return f"rk{n}_{name}"

        st.markdown(f"##### 🧪 평가 대상: {src.get('name') or '(미입력)'} "
                    f"〔{src.get('source', '')}〕")

        # ── 1. 기본정보 ──
        st.markdown("###### 1. 평가 대상 화학물질 기본정보")
        c1, c2, c3 = st.columns([1.6, 1.2, 0.9])
        rk_name = c1.text_input("제품명 〔MSDS 1항〕", src.get("name", ""),
                                key=_k("name"))
        rk_mf = c2.text_input("제조사 〔MSDS 1항〕", src.get("manufacturer", ""),
                              key=_k("mf"))
        rk_rev = c3.text_input("MSDS 최신개정일자", src.get("revision", ""),
                               key=_k("rev"), placeholder="YYYY-MM-DD")
        comp_rows = st.data_editor(
            [{"성분명": c.get("name", ""), "CAS 번호": c.get("cas", ""),
              "함유량": c.get("content", "")}
             for c in src.get("components") or []] or
            [{"성분명": "", "CAS 번호": "", "함유량": ""}],
            num_rows="dynamic", key=_k("comps"), use_container_width=True)
        rk_comps = [{"name": (r.get("성분명") or "").strip(),
                     "cas": (r.get("CAS 번호") or "").strip(),
                     "content": (r.get("함유량") or "").strip()}
                    for r in comp_rows
                    if (r.get("성분명") or r.get("CAS 번호") or
                        r.get("함유량") or "").strip()]
        c1, c2, c3 = st.columns(3)
        rk_dept = c1.text_input("취급부서 / 공정", key=_k("dept"))
        rk_store = c2.text_input("저장·보관(예정) 장소", key=_k("store"))
        rk_purpose = c3.text_input("도입 배경 or 목적", key=_k("purpose"))
        rk_hcodes = st.text_input(
            "★ H-Code (유해위험문구) 〔MSDS 2항 — 자동 인식, 수정 가능〕",
            src.get("hcodes", ""), key=_k("hcodes"),
            help="쉼표/공백으로 구분. H314·H340·H350·H360은 구분까지 표기 "
                 "(예: H350 Cat1A). 자동 인식 시 구분 1만 있으면 보수적으로 "
                 "1A로 채웁니다.")

        # ── 2. MSDS 세션별 데이터 ──
        st.markdown("###### 2. MSDS 세션별 데이터 〔8·9·11·12항 자동 인식, "
                    "나머지 직접 입력〕")
        auto_vals = src.get("vals") or {}
        rk_vals = {"hcodes": rk_hcodes}
        with st.expander("H-Code 자동 판정 결과 (①기초Data D23~D40)"):
            ac = RL.auto_codes(rk_hcodes)
            st.dataframe([{"항목": RL.AUTO_LABELS[k], "판정": v}
                          for k, v in ac.items() if v != "없음"] or
                         [{"항목": "-", "판정": "해당 없음"}],
                         hide_index=True, use_container_width=True)
        for grp_label, keys in RL.RISK_GROUPS:
            st.markdown(f"**▶ {grp_label}**")
            cols = st.columns(4)
            for i, key in enumerate(keys):
                _, cell, label, kind, unit, sec = RL.RISK_FIELD_BY_KEY[key]
                auto = str(auto_vals.get(key, "") or "")
                full = f"{label}" + (f" ({unit})" if unit else "")
                with cols[i % 4]:
                    if kind == "select":
                        opts = RL.SELECT_OPTIONS[key]
                        idx = opts.index(auto) if auto in opts else 0
                        rk_vals[key] = st.selectbox(full, opts, index=idx,
                                                    key=_k(key))
                    else:
                        rk_vals[key] = st.text_input(
                            full, auto, key=_k(key), placeholder="없음",
                            help=f"MSDS {sec} — 숫자만 입력, 없으면 비워두세요"
                                 + (" (자동 인식됨)" if auto else ""))

        refs = RL.ref_scores(rk_vals)

        # ── 3. 분야별 평가 (②③④) ──
        st.markdown("###### 3. 분야별 위험성평가 — 유해성 점수는 [참고값]으로 "
                    "미리 채워지며 조정할 수 있습니다")
        if st.button("🔄 유해성 점수를 현재 [참고값]으로 재설정",
                     key=_k("score_reset_btn")):
            st.session_state.risk_score_reset = \
                st.session_state.get("risk_score_reset", 0) + 1
        rn = st.session_state.get("risk_score_reset", 0)

        # 가능성 공통 입력 — 취급 횟수·1회 취급량은 ②③④ 세 분야 공통 적용
        st.markdown("**가능성 공통 입력** — 취급 횟수와 1회 취급량은 한 번만 "
                    "입력하면 물리화학·환경오염·작업자 안전보건 세 분야에 모두 "
                    "반영됩니다 (분야별 ③ 환경 항목만 각각 선택)")
        cc = st.columns(2)
        common_poss = []
        for i, (plabel, popt) in enumerate(
                [("① 취급 횟수 (공통)", RL.POSS_FREQ),
                 ("② 1회 취급량 (공통)", RL.POSS_AMOUNT)]):
            disp = ["(선택)"] + [f"{j + 1}점 — {o}".replace("\n", " ")
                                for j, o in enumerate(popt)]
            sel = cc[i].selectbox(plabel, range(len(disp)),
                                  format_func=lambda x, d=disp: d[x],
                                  key=_k(f"pc_{i}"))
            common_poss.append(sel - 1 if sel > 0 else None)

        sheets_payload = {}
        summary_rows = []
        for skey, meta in RL.SHEETS.items():
            with st.expander(f"{meta['title']}", expanded=False):
                scores, notes = [], []
                for i, (grp, item) in enumerate(meta["items"]):
                    r = refs[skey][i]
                    a, b, c, dcol = st.columns([2.4, 0.7, 0.8, 1.6])
                    a.markdown(f"**{i + 1}. [{grp}]** {item}")
                    b.markdown(f"참고값: **{r if r else '—'}**")
                    sc = c.selectbox("유해성 점수", [1, 2, 3, 4, 5],
                                     index=(r or 1) - 1,
                                     key=_k(f"{skey}s{rn}_{i}"),
                                     label_visibility="collapsed")
                    note = dcol.text_input(
                        "비고", key=_k(f"{skey}note_{i}"),
                        placeholder="참고값과 다르게 평가한 사유",
                        label_visibility="collapsed")
                    scores.append(sc)
                    notes.append(note.strip())
                st.markdown("**가능성 산정** — ① 취급 횟수·② 1회 취급량은 "
                            "위의 공통 입력이 자동 반영됩니다")
                popts = RL.poss_options(skey)
                disp = ["(선택)"] + [
                    f"{j + 1}점 — {o}".replace("\n", " ")
                    for j, o in enumerate(popts[2])]
                sel = st.selectbox(meta["poss_labels"][2], range(len(disp)),
                                   format_func=lambda x, d=disp: d[x],
                                   key=_k(f"{skey}p_2"))
                poss = [common_poss[0], common_poss[1],
                        sel - 1 if sel > 0 else None]

                # 저감대책 선택 (⑥ 저감대책DB)
                st.markdown("**위험성 저감대책** — 허용 불가(위험도 9 이상)면 "
                            "필수, 각 위계에서 최대 3개")
                mit = {}
                mcols = st.columns(4 if meta["has_ppe"] else 3)
                ti = 0
                for tier, tlabel, tkor in RL.TIERS:
                    if tier == "ppe" and not meta["has_ppe"]:
                        continue
                    opts = [d["no"] for d in RL.RISK_DB
                            if d["field"] == meta["field"] and
                            d["tier"] == tkor]
                    mit[tier] = mcols[ti].multiselect(
                        tlabel, opts, key=_k(f"{skey}m_{tier}"),
                        max_selections=3,
                        format_func=lambda no: (
                            f"{no} ({RL.RISK_DB_BY_NO[no]['reduce']}) "
                            f"{RL.RISK_DB_BY_NO[no]['text']}"))
                    ti += 1

                sheets_payload[skey] = {"scores": scores, "notes": notes,
                                        "poss": poss, "mit": mit}

        result = RL.evaluate(rk_vals, sheets_payload)

        for skey, meta in RL.SHEETS.items():
            sres = result["sheets"][skey]
            sh = sheets_payload[skey]
            with st.expander(f"📊 {meta['title']} — 결과: 위험도 "
                             f"{sres['final_risk']} ({sres['final_level']})",
                             expanded=True):
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("유해성 등급", sres["hazard"]["grade"],
                          help=f"합계 {sres['hazard']['total']} + 가중치 "
                               f"{sres['hazard']['weight']} = "
                               f"{sres['hazard']['final']}점")
                m2.metric("가능성 등급 (전)", sres["poss_grade"],
                          help=f"가능성 점수 {sres['poss_score']}점")
                m3.metric("위험도 (전)", f"{sres['risk']} ({sres['level']})")
                m4.metric("가능성 등급 (저감 후)", sres["mit"]["new_grade"],
                          help=f"저감 {sres['mit']['reduction']:+.2f}점 → "
                               f"{sres['mit']['new_score']:.2f}점")
                m5.metric("최종 위험도", f"{sres['final_risk']} "
                                        f"({sres['final_level']})")
                if sres["poss_missing"]:
                    st.warning("가능성 평가 항목(공통 2개 + 환경 1개)을 모두 "
                               "선택해 주세요.")
                if sres["final_allow"]:
                    st.success("✅ 허용 가능 (위험도 8 이하)")
                elif sres["final_level"] == "고":
                    st.warning("🟠 고위험 — 부서장 검토 및 안전보건관리책임자 "
                               "승인 하에 도입/취급 가능 (저감대책 보강 권장)")
                else:
                    st.error("🔴 허용 불가 — 저감대책을 적용해 위험도를 낮춘 "
                             "후 도입 가능")
                # 고위험 항목 추천 저감대책
                recs = []
                for i, (grp, item) in enumerate(meta["items"]):
                    if sh["scores"][i] >= 4:
                        recs.append((f"유해성 {i + 1}. {item}",
                                     sh["scores"][i], meta["rec"][i]))
                for j, pl in enumerate(meta["poss_labels"]):
                    pv = sh["poss"][j]
                    if pv is not None and pv + 1 >= 4:
                        recs.append((f"가능성 {pl}", pv + 1,
                                     meta["rec"][8 + j]))
                if recs:
                    st.markdown("**[참고] 고위험 항목(4점↑) 추천 저감대책**")
                    st.dataframe(
                        [{"항목": nm, "점수": sc,
                          "공학": rec[0] or "—", "운영": rec[1] or "—",
                          "행정": rec[2] or "—", "보호구": rec[3] or "—"}
                         for nm, sc, rec in recs],
                        hide_index=True, use_container_width=True)
            summary_rows.append({
                "분야": meta["title"][2:], "유해성 등급": sres["hazard"]["grade"],
                "가능성 등급(전)": sres["poss_grade"],
                "가능성 등급(후)": sres["mit"]["new_grade"],
                "위험수준/위험도": f"{sres['final_level']} / "
                                   f"{sres['final_risk']}",
                "치명 항목 수": str(sres["hazard"]["fatal"] or "")})

        # ── 4. 종합결과 ──
        st.divider()
        st.markdown("###### 4. 종합결과")
        st.dataframe(summary_rows, hide_index=True, use_container_width=True)
        verdict = result["verdict"]
        (st.error if "허용 불가" in verdict
         else st.warning if "고위험" in verdict or "중위험" in verdict
         else st.success)(verdict)
        st.caption(RL.OVERALL_CRITERIA)
        c1, c2, c3, c4 = st.columns(4)
        ev_type = c1.text_input("평가유형", key=_k("evtype"),
                                placeholder="예: 신규 도입")
        ev_date = c2.date_input("평가일자", value=None, key=_k("evdate"),
                                format="YYYY-MM-DD")
        ev_dept = c3.text_input("평가부서", key=_k("evdept"))
        ev_by = c4.text_input("평가자", key=_k("evby"))
        opinion = st.text_area("[기안] 평가자 의견", key=_k("opinion"),
                               height=80)

        payload = {
            "basic": {"name": rk_name.strip(), "manufacturer": rk_mf.strip(),
                      "revision": rk_rev.strip(), "components": rk_comps,
                      "dept": rk_dept.strip(), "storage": rk_store.strip(),
                      "purpose": rk_purpose.strip(),
                      "hcodes": rk_hcodes.strip()},
            "vals": rk_vals, "sheets": sheets_payload,
            "meta": {"ev_type": ev_type.strip(),
                     "ev_date": str(ev_date) if ev_date else "",
                     "ev_dept": ev_dept.strip(), "ev_by": ev_by.strip(),
                     "opinion": opinion.strip()}}
        with open(_RISK_TPL_PATH, "rb") as _tf:
            _tpl = _tf.read()
        st.download_button(
            "⬇️ 위험성평가 엑셀 다운로드 (양식 자동 작성)",
            RL.fill_template(_tpl, payload),
            file_name=f"화학물질_위험성평가_{rk_name.strip() or '미입력'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary",
            help="첨부 양식과 동일한 수식·서식의 엑셀 파일에 입력값이 자동 "
                 "기입됩니다. 엑셀에서 열면 수식이 재계산되어 화면과 동일한 "
                 "결과가 표시됩니다.")

if menu == _MENUS[3]:
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

    if "sign_subs" not in st.session_state:
        st.session_state.sign_subs = []      # [{"id", "name", "cas", "un", "pictograms"}]
        st.session_state.sign_seq = 0

    def _add_sub(ent):
        st.session_state.sign_seq += 1
        st.session_state.sign_subs.append(
            {"id": st.session_state.sign_seq, "name": ent.get("name", ""),
             "cas": ent.get("cas", ""), "un": ent.get("un", ""),
             "pictograms": list(ent.get("pictograms") or [])})

    # ── 화학물질 추가: 물질명 입력 → CAS·UN·그림문자 자동 입력 ──
    st.markdown("###### 화학물질 추가 — 물질명을 입력하면 CAS 번호·국제연합번호·"
                "그림문자가 자동 입력됩니다")
    st.caption(f"내장 물질정보 {len(CHEM_DB)}종(물질명·별칭·CAS 번호로 검색)은 참고용 "
               "요약이므로, 표지 제작 전에 해당 제품의 MSDS와 대조해 확인하세요. "
               "추가한 뒤 모든 항목을 직접 수정할 수 있습니다. CAS 번호는 교차 "
               "확인용 조회 정보로, 표지판에는 표기되지 않습니다.")
    s1, s2 = st.columns([3, 1])
    chem_q = s1.text_input("화학물질명", key="chem_q",
                           placeholder="예: 황산, 톨루엔, 가성소다, 7664-93-9")
    if s2.button("🔎 검색 · 추가", type="primary"):
        found = search_chem(chem_q)
        if not chem_q.strip():
            st.session_state.chem_results = []
            st.session_state.chem_msg = ("warning", "화학물질명을 입력해 주세요.")
        elif len(found) == 1:
            _add_sub(found[0])
            st.session_state.chem_results = []
            st.session_state.chem_msg = \
                ("success", f"「{found[0]['name']}」을(를) 표에 추가했습니다 — "
                            f"CAS {found[0]['cas']}, UN {found[0]['un'] or '없음'}, "
                            f"그림문자 {', '.join(found[0]['pictograms']) or '없음'}")
        elif found:
            st.session_state.chem_results = found
            st.session_state.chem_msg = \
                ("info", f"{len(found)}건이 검색되었습니다 — 아래에서 물질을 선택하세요.")
        else:
            _add_sub({"name": chem_q.strip()})
            st.session_state.chem_results = []
            st.session_state.chem_msg = \
                ("warning", f"내장 물질정보에서 「{chem_q.strip()}」을(를) 찾지 못해 "
                            "물질명만 추가했습니다. 아래에서 CAS 번호·국제연합번호·"
                            "그림문자를 직접 입력해 주세요.")
    kind, msg = st.session_state.get("chem_msg", ("", ""))
    if msg:
        getattr(st, kind)(msg)
    for i, ent in enumerate(st.session_state.get("chem_results", [])):
        r1, r2 = st.columns([5, 1])
        r1.markdown(f"**{ent['name']}** — CAS {ent['cas']} · "
                    f"국제연합번호: {ent['un'] or '없음'} · "
                    f"그림문자: {', '.join(ent['pictograms']) or '없음'}")
        if r2.button("표에 추가", key=f"chem_add_{i}"):
            _add_sub(ent)
            st.session_state.chem_results = []
            st.session_state.chem_msg = \
                ("success", f"「{ent['name']}」을(를) 표에 추가했습니다.")
            st.rerun()

    # ── 추가한 물질 목록 (모든 항목 수정 가능) ──
    entries = []
    if st.session_state.sign_subs:
        st.markdown("###### 표에 들어갈 물질 — 항목을 자유롭게 수정할 수 있습니다")
    for ent in list(st.session_state.sign_subs):
        sid = ent["id"]
        e1, e2, e3, e4 = st.columns([2, 1.2, 1, 0.5])
        ent["name"] = e1.text_input("물질명", ent["name"], key=f"sub_nm_{sid}")
        ent["cas"] = e2.text_input("CAS 번호 (확인용)", ent["cas"],
                                   key=f"sub_cas_{sid}",
                                   help="교차 확인용 — 표지판에는 표기되지 않습니다.")
        ent["un"] = e3.text_input("국제연합번호(UN No.)", ent["un"],
                                  key=f"sub_un_{sid}")
        e4.markdown("<div style='height:1.9em'></div>", unsafe_allow_html=True)
        if e4.button("🗑️", key=f"sub_del_{sid}", help="이 물질 삭제"):
            st.session_state.sign_subs = \
                [s for s in st.session_state.sign_subs if s["id"] != sid]
            st.rerun()
        pics = st.multiselect("그림문자", _PIC_OPTIONS,
                              default=[_pic_label(c) for c in ent["pictograms"]
                                       if c in PICTOGRAM_NAMES],
                              key=f"sub_pic_{sid}")
        ent["pictograms"] = [p.split()[0] for p in pics]
        entries.append(ent)
    if not entries:
        st.info("위에서 화학물질명을 검색해 물질을 추가하면 표지판 표에 채워집니다.")

    svg = build_sign_svg(entries, manager, phone, phone2)
    st.download_button("⬇️ 표지판 시안 다운로드 (SVG, 실측 75×50cm+표)", svg,
                       file_name="유해화학물질_표지판.svg", mime="image/svg+xml")
    preview_svg = re.sub(r'width="[^"]+" height="[^"]+"', 'width="100%"',
                         svg, count=1)   # 화면에서는 폭에 맞춰 축소 표시
    st.markdown(
        f'<div style="border:1px solid #ccc;background:#fff;padding:10px;">'
        f'{preview_svg}</div>', unsafe_allow_html=True)
