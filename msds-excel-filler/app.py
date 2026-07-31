# -*- coding: utf-8 -*-
"""MSDS PDF → 화학물질 작업공정별 관리 요령 엑셀 자동 작성 웹 앱.

실행:  streamlit run app.py
"""
import datetime
import hashlib
import io
import json
import os
import re
import shutil

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

st.set_page_config(page_title="켐세이프 — 화학물질 통합 안전관리",
                   page_icon="🧪", layout="wide")

st.title("🧪 켐세이프 (ChemSafe) — 화학물질 통합 안전관리 도구")
st.caption("「대시보드」에서 연간 도입검토·정보등록·위험성평가 현황을 확인하고, "
           "「화학물질 작업공정별 관리요령」 메뉴에서 MSDS PDF를 업로드하면 항목을 자동 "
           "추출해 엑셀 양식을 만들고, 「화학물질 도입검토」 메뉴에서는 MSDS에서 물질명·"
           "제조사·주요성분을 자동 인식해 도입검토·정보등록 대상 여부를 판독하고 누적 "
           "관리하며, 「화학물질 위험성평가」 메뉴에서는 도입검토 대상 물질의 위험성평가를 "
           "작성해 평가 양식 엑셀로 내려받고, 「유해화학물질 규격표지」 메뉴에서는 "
           "화학물질명만 입력하면 CAS 번호·국제연합번호·그림문자가 자동 입력된 표지판 "
           "시안(화학물질관리법 시행규칙 별표 2)을 만들며, 「도급신고」 메뉴에서는 "
           "도급 업체의 계약·도급기간과 수리공문을 등록해 만료 1개월 전 알람과 함께 "
           "누적 관리합니다.")

_PIC_OPTIONS = [f"{code} {name}" for code, name in PICTOGRAM_NAMES.items()]


def _pic_label(code: str) -> str:
    return f"{code} {PICTOGRAM_NAMES.get(code, '')}"


# ── 🔐 로그인 — 아이디별 데이터 저장, 같은 아이디는 등록·이력을 공유 ──
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_USERS_PATH = os.path.join(_APP_DIR, "users.json")


def _load_users():
    try:
        with open(_USERS_PATH, encoding="utf-8") as f:
            u = json.load(f)
            return u if isinstance(u, dict) else {}
    except Exception:
        return {}


if "login_id" not in st.session_state:
    st.session_state.login_id = None
if not st.session_state.login_id:
    st.markdown("#### 🔐 로그인")
    st.caption("아이디별로 데이터가 저장됩니다 — **같은 아이디로 로그인하면 "
               "여러 사람이 작성한 도입검토 등록·위험성평가 이력을 함께 "
               "조회**할 수 있습니다(팀 공용 아이디 권장). 처음 쓰는 아이디는 "
               "입력한 비밀번호로 자동 등록됩니다.")
    lc1, lc2, lc3 = st.columns([1.3, 1.3, 0.8])
    l_id = lc1.text_input("아이디", key="login_uid",
                          placeholder="예: 환경안전팀")
    l_pw = lc2.text_input("비밀번호", type="password", key="login_pw")
    lc3.markdown("<div style='height:1.75em'></div>", unsafe_allow_html=True)
    if lc3.button("로그인", key="login_btn", type="primary"):
        uid = (l_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_\-가-힣]{2,20}", uid):
            st.error("아이디는 2~20자의 한글·영문·숫자·하이픈(-)·밑줄(_)만 "
                     "쓸 수 있습니다.")
        elif not l_pw:
            st.error("비밀번호를 입력하세요.")
        else:
            users = _load_users()
            pw_hash = hashlib.sha256(l_pw.encode("utf-8")).hexdigest()
            if uid not in users:
                # 오타로 새 아이디가 조용히 만들어져 "자료가 사라진 것처럼"
                # 보이는 일을 막는다 — 한 번 더 눌러 신규 등록을 확인.
                if st.session_state.get("login_new_pending") != uid:
                    st.session_state.login_new_pending = uid
                    known = ", ".join(users) if users else ""
                    st.warning(f"「{uid}」는 등록되지 않은 아이디입니다."
                               + (f" (등록된 아이디: {known})" if known
                                  else "")
                               + " 기존 자료를 보려면 쓰던 아이디로 로그인"
                               "하세요. 이 아이디로 새로 등록하려면 "
                               "「로그인」을 한 번 더 누르세요.")
                else:
                    users[uid] = pw_hash
                    with open(_USERS_PATH, "w", encoding="utf-8") as f:
                        json.dump(users, f, ensure_ascii=False, indent=1)
                    st.session_state.login_new_pending = None
                    st.session_state.login_id = uid
                    st.rerun()
            elif users[uid] == pw_hash:
                st.session_state.login_new_pending = None
                st.session_state.login_id = uid
                st.rerun()
            else:
                st.error("비밀번호가 일치하지 않습니다.")
    st.stop()

_uid = st.session_state.login_id
_lc1, _lc2 = st.columns([6, 1])
_lc1.caption(f"👤 **{_uid}** 로그인 중 — 같은 아이디로 로그인한 모든 "
             "사용자가 등록·이력을 함께 봅니다.")
if _lc2.button("로그아웃", key="logout_btn"):
    st.session_state.login_id = None
    st.rerun()


# 메뉴 — 라디오 내비게이션 (도입검토 → 위험성평가 버튼으로 이동할 수 있도록
# st.tabs 대신 사용: 프로그램에서 st.session_state.menu 변경으로 전환 가능)
M_DASH = "🏠 대시보드"
M_MANAGE = "📋 화학물질 작업공정별 관리요령"
M_REVIEW = "🔍 화학물질 도입검토"
M_RISK = "🧪 화학물질 위험성평가"
M_SIGN = "🚧 유해화학물질 규격표지"
M_CONTRACT = "📑 도급신고"
_MENUS = [M_DASH, M_MANAGE, M_REVIEW, M_RISK, M_SIGN, M_CONTRACT]
if "menu" not in st.session_state:
    st.session_state.menu = M_DASH
if st.session_state.get("menu_jump"):     # 버튼으로 메뉴 이동 (다음 실행에 반영)
    st.session_state.menu = st.session_state.pop("menu_jump")
menu = st.radio("메뉴", _MENUS, horizontal=True, key="menu",
                label_visibility="collapsed")
st.markdown("<hr style='margin:0.2rem 0 1rem 0;'>", unsafe_allow_html=True)

# 도입검토 등록 DB (누적 관리) — 대시보드·도입검토·위험성평가 메뉴 공용.
# 아이디별 파일로 저장해 같은 아이디로 로그인하면 함께 조회된다.
_REVIEW_DB_PATH = os.path.join(_APP_DIR, f"review_db_{_uid}.json")
_RISK_DB_PATH = os.path.join(_APP_DIR, f"risk_db_{_uid}.json")
_LEGACY_REVIEW = os.path.join(_APP_DIR, "review_db.json")
if not os.path.exists(_REVIEW_DB_PATH) and os.path.exists(_LEGACY_REVIEW):
    shutil.copyfile(_LEGACY_REVIEW, _REVIEW_DB_PATH)   # 로그인 도입 전 데이터


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


def _load_risk_db():
    """완료·작성중 위험성평가 이력 (아이디별 공유)."""
    try:
        with open(_RISK_DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
            return db if isinstance(db, list) else []
    except Exception:
        return []


def _save_risk_db(db):
    with open(_RISK_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)


# ── 📑 도급신고 DB (아이디별 공유) ──
_CONTRACT_DB_PATH = os.path.join(_APP_DIR, f"contract_db_{_uid}.json")
_CT_OPTS_PATH = os.path.join(_APP_DIR, f"ct_options_{_uid}.json")
CT_TYPES = ["1회성계약", "연간계약", "기타"]
CT_FACILITIES = ["1CC 암모니아수", "2CC 암모니아수", "1CC 황산", "2CC 황산",
                 "염산", "수산화나트륨", "메탄올", "실험실",
                 "1CC SWAS", "2CC SWAS"]
CT_SUBSTANCES = ["암모니아수", "황산", "염산", "수산화나트륨", "메탄올",
                 "디이소프로필아민", "질산은"]


def _load_ct_opts():
    """직접 추가한 취급시설·취급물질 (아이디별 저장)."""
    try:
        with open(_CT_OPTS_PATH, encoding="utf-8") as f:
            o = json.load(f)
            return {"facilities": list(o.get("facilities") or []),
                    "substances": list(o.get("substances") or [])}
    except Exception:
        return {"facilities": [], "substances": []}


def _save_ct_opts(opts):
    with open(_CT_OPTS_PATH, "w", encoding="utf-8") as f:
        json.dump(opts, f, ensure_ascii=False, indent=1)


def _load_contract_db():
    try:
        with open(_CONTRACT_DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
            return db if isinstance(db, list) else []
    except Exception:
        return []


def _save_contract_db(db):
    with open(_CONTRACT_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)


def _ct_days_left(r):
    """도급기간 만료일까지 남은 일수 (만료일 미입력이면 None)."""
    try:
        d = datetime.date.fromisoformat(r.get("dogub_end") or "")
    except ValueError:
        return None
    return (d - datetime.date.today()).days


def _ct_status(days):
    if days is None:
        return ""
    if days < 0:
        return "만료"
    return "만료임박" if days <= 30 else "정상"


def _ct_period(a, b):
    return f"{a or ''} ~ {b or ''}".strip(" ~") if (a or b) else ""


# ── 🏠 대시보드 ─────────────────────────────────────────────────────────
def _rv_disp_label(r, key):
    """담당자 검토 결과 '대상 아님' 체크 시 표시 문구."""
    return "대상 아님(담당자 검토)" if r.get("override") else r.get(key, "")


def _dash_stats(db):
    """연도별 도입검토·정보등록·위험성평가 완료 건수 (담당자 검토 제외 반영)."""
    stats = {}
    for r in db:
        if r.get("override"):
            continue
        y = (r.get("date") or "")[:4] or "미상"
        s = stats.setdefault(y, {"review": 0, "register": 0, "done": 0})
        if r.get("review") == "도입검토 대상":
            s["review"] += 1
            if r.get("risk_done"):
                s["done"] += 1
        if r.get("register") == "정보등록 대상":
            s["register"] += 1
    return stats


_CI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "ci.png")

if menu == M_DASH:
    if os.path.exists(_CI_PATH):                  # 회사 CI
        st.image(_CI_PATH, width=229)
    _db = _load_review_db()
    stats = _dash_stats(_db)
    ty = str(datetime.date.today().year)
    cur = stats.get(ty, {"review": 0, "register": 0, "done": 0})
    st.markdown("##### 🏠 대시보드 — 도입검토 · 정보등록 · 위험성평가 현황")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{ty}년 도입검토 건수", cur["review"],
              help="올해 작성일 기준, 도입검토 대상으로 등록된 건수")
    c2.metric(f"{ty}년 정보등록 건수", cur["register"],
              help="올해 작성일 기준, 정보등록 대상으로 등록된 건수")
    c3.metric(f"{ty}년 위험성평가 완료", f"{cur['done']} / {cur['review']}",
              help="도입검토 대상 중 위험성평가를 완료(엑셀 다운로드)한 건수")
    c4.metric("누적 등록", len(_db))
    year_rows = [{"연도": y, "도입검토 건수": s["review"],
                  "정보등록 건수": s["register"],
                  "위험성평가 완료": s["done"],
                  "위험성평가 미실시": s["review"] - s["done"]}
                 for y, s in sorted(stats.items(), reverse=True)]
    if year_rows:
        st.markdown("###### 연도별 현황")
        st.dataframe(year_rows, hide_index=True, use_container_width=True)
        st.caption("등록된 화학물질(도입검토 메뉴)의 작성일 기준 집계입니다. "
                   "담당자 검토 결과 '대상 아님'으로 체크된 등록은 집계에서 "
                   "제외됩니다.")
    else:
        st.info("아직 등록된 화학물질이 없습니다 — 「화학물질 도입검토」 "
                "메뉴에서 MSDS를 등록하면 여기에 집계됩니다.")

    # ── 📑 도급신고 현황판 ──
    st.markdown("##### 📑 도급신고 현황판")
    _ct_db = _load_contract_db()
    _ct_rows = [(r, _ct_days_left(r)) for r in _ct_db]
    _ct_imm = [(r, d) for r, d in _ct_rows if _ct_status(d) == "만료임박"]
    _ct_exp = [(r, d) for r, d in _ct_rows if _ct_status(d) == "만료"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("등록 업체", len(_ct_db))
    k2.metric("도급기간 정상", sum(1 for _, d in _ct_rows
                                   if _ct_status(d) == "정상"))
    k3.metric("만료 1개월 이내", len(_ct_imm))
    k4.metric("만료", len(_ct_exp))
    if _ct_imm:
        st.error("🔔 **도급기간 만료 1개월 이내 업체 "
                 f"{len(_ct_imm)}곳** — 재계약 또는 도급신고 갱신이 "
                 "필요합니다: " +
                 ", ".join(f"{r.get('company', '')}"
                           f"(만료 {r.get('dogub_end', '')}, D-{d})"
                           for r, d in _ct_imm))
        st.dataframe(
            [{"업체명": r.get("company", ""),
              "계약종류": r.get("ctype", ""),
              "도급기간": _ct_period(r.get("dogub_start"),
                                     r.get("dogub_end")),
              "남은 일수": f"D-{d}",
              "취급시설": r.get("facility", ""),
              "취급물질": r.get("substance", "")} for r, d in _ct_imm],
            hide_index=True, use_container_width=True)
    elif _ct_db:
        st.success("도급기간 만료 1개월 이내 업체가 없습니다.")
    else:
        st.caption("등록된 도급신고 업체가 없습니다 — 「도급신고」 메뉴에서 "
                   "등록하면 여기에 집계되고, 도급기간 만료 1개월 이내 업체가 "
                   "알람으로 표시됩니다.")

uploaded = None
if menu == M_MANAGE:
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
if menu == M_MANAGE:
    for name in list(st.session_state.parsed):
        if name not in current_names:
            del st.session_state.parsed[name]

records = []
for name, data in (st.session_state.parsed.items()
                   if menu == M_MANAGE else []):
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

if menu == M_MANAGE:
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
                "주요성분 및 함량", "도입검토", "정보등록", "위험성평가",
                "MSDS 파일"],
               [[r.get("id"), r.get("date", ""), r.get("name", ""),
                 r.get("manufacturer", ""), r.get("revision", ""),
                 components_text(r.get("components", [])),
                 _rv_disp_label(r, "review"), _rv_disp_label(r, "register"),
                 (f"완료 ({r['risk_done']})" if r.get("risk_done") else ""),
                 r.get("source", "")] for r in db],
               [6, 12, 30, 22, 14, 50, 16, 16, 16, 30])
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


if menu == M_REVIEW:
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
                        "register": res["register_label"],
                        # 위험성평가 연계용 — MSDS 인식 데이터·진행 상태
                        "hcodes": data.hcodes, "risk": dict(data.risk),
                        "risk_done": "", "override": False})
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
        _db_cols = ["No.", "작성일", "화학물질명", "제조사", "MSDS 개정일자",
                    "주요성분 및 함량", "도입검토", "정보등록", "위험성평가",
                    "MSDS 파일"]
        edited = st.data_editor(
            [{"No.": r.get("id"), "작성일": r.get("date", ""),
              "화학물질명": r.get("name", ""),
              "제조사": r.get("manufacturer", ""),
              "MSDS 개정일자": r.get("revision", ""),
              "주요성분 및 함량": components_text(r.get("components", [])),
              "도입검토": _rv_disp_label(r, "review"),
              "정보등록": _rv_disp_label(r, "register"),
              "위험성평가": (f"✅ 위험성평가 완료 ({r['risk_done']})"
                             if r.get("risk_done") else
                             ("대상 (미실시)" if not r.get("override") and
                              r.get("review") == "도입검토 대상" else "")),
              "도입검토 대상 아님": bool(r.get("override")),
              "MSDS 파일": r.get("source", "")} for r in shown],
            hide_index=True, use_container_width=True, key="rv_db_edit",
            disabled=_db_cols,
            column_config={"도입검토 대상 아님":
                           st.column_config.CheckboxColumn(
                               help="도입검토·정보등록 대상으로 판정되었지만 "
                                    "담당자 검토 결과 대상이 아니면 체크하세요 "
                                    "— 표시가 '대상 아님(담당자 검토)'으로 "
                                    "바뀌고 대시보드 집계에서 제외됩니다.")})
        _ovr_changed = False
        for row in edited:
            rec = next((r for r in review_db if r.get("id") == row["No."]),
                       None)
            if rec is not None and \
                    bool(rec.get("override")) != bool(row["도입검토 대상 아님"]):
                rec["override"] = bool(row["도입검토 대상 아님"])
                _ovr_changed = True
        if _ovr_changed:
            _save_review_db(review_db)
            st.rerun()

        # 도입검토 대상 → 「위험성 평가」 (담당자 검토 '대상 아님' 제외)
        risk_targets = [r for r in shown
                        if r.get("review") == "도입검토 대상" and
                        not r.get("override")]
        if risk_targets:
            rk1, rk2 = st.columns([1.8, 1.6])

            def _rt_label(i):
                r = next(x for x in risk_targets if x.get("id") == i)
                return (f"{i} — {r.get('name', '')}" +
                        (" (위험성평가 완료)" if r.get("risk_done") else ""))
            rt_id = rk1.selectbox("위험성평가 대상 (도입검토 대상 등록)",
                                  [r.get("id") for r in risk_targets],
                                  format_func=_rt_label, key="rv_risk_sel")
            rk2.markdown("<div style='height:1.75em'></div>",
                         unsafe_allow_html=True)
            if rk2.button("🧪 위험성 평가 — 선택한 등록으로 작성",
                          key="rv_db_risk",
                          help="등록된 MSDS 인식 결과를 가지고 「화학물질 "
                               "위험성평가」 메뉴로 이동합니다. 위험성평가 "
                               "엑셀을 다운로드하면 이 목록에 '위험성평가 "
                               "완료'로 표시됩니다."):
                rec = next(r for r in risk_targets if r.get("id") == rt_id)
                st.session_state.risk_nonce = \
                    st.session_state.get("risk_nonce", 0) + 1
                st.session_state.risk_score_reset = 0
                st.session_state.risk_hist_id = None
                st.session_state.risk_src = {
                    "name": rec.get("name", ""),
                    "manufacturer": rec.get("manufacturer", ""),
                    "revision": rec.get("revision", ""),
                    "components": rec.get("components", []),
                    "hcodes": rec.get("hcodes", ""),
                    "vals": dict(rec.get("risk") or {}),
                    "source": rec.get("source", ""),
                    "db_id": rec.get("id")}
                st.session_state.menu_jump = M_RISK
                st.rerun()
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

if menu == M_RISK:
    st.markdown("도입검토 대상 화학물질의 **위험성평가**(물리화학적 · 환경오염 · "
                "작업자 안전보건, 유해성×가능성)를 작성합니다. MSDS에서 자동 "
                "인식한 값(H-Code·물리화학 특성·독성·환경 데이터)이 미리 채워지며, "
                "자동 인식되지 않은 항목은 직접 입력합니다. 완성된 평가는 "
                "**위험성평가 엑셀 양식**으로 내려받을 수 있습니다(양식 수식·서식 "
                "그대로 유지).")

    # ── 🗂 위험성평가 이력 조회 (완료·작성중 — 아이디별 공유) ──
    _rk_db = _load_risk_db()
    with st.expander(f"🗂 위험성평가 이력 조회 ({len(_rk_db)}건 — 완료·작성중)",
                     expanded=bool(_rk_db) and
                     not st.session_state.get("risk_src")):
        if not _rk_db:
            st.caption("저장된 위험성평가가 없습니다 — 아래에서 작성 후 "
                       "「작성 완료」 또는 「저장」을 누르면 이력에 보관됩니다.")
        else:
            st.dataframe(
                [{"No.": r.get("id"), "상태": r.get("status", ""),
                  "물질명": r.get("name", ""),
                  "최종 위험도(최대)": r.get("max_risk", ""),
                  "종합 판정": r.get("verdict", ""),
                  "저장일시": r.get("saved_at", ""),
                  "MSDS 파일": r.get("source", "")} for r in _rk_db],
                hide_index=True, use_container_width=True)
            _hsel = st.selectbox(
                "이력 선택 (No.)", [r.get("id") for r in _rk_db],
                format_func=lambda i: next(
                    (f"{i} — {r.get('name', '')} [{r.get('status', '')}] "
                     f"{r.get('saved_at', '')}"
                     for r in _rk_db if r.get("id") == i), str(i)),
                key="rk_hist_sel")
            _hrec = next((r for r in _rk_db if r.get("id") == _hsel), None)
            hb1, hb2, hb3 = st.columns([1.2, 1.4, 0.9])
            if hb1.button("📂 불러오기 (이어서 작성·수정)", key="rk_hist_load"):
                _pb = _hrec.get("payload", {}).get("basic", {})
                st.session_state.risk_nonce = \
                    st.session_state.get("risk_nonce", 0) + 1
                st.session_state.risk_score_reset = 0
                st.session_state.risk_src = {
                    "name": _pb.get("name", ""),
                    "manufacturer": _pb.get("manufacturer", ""),
                    "revision": _pb.get("revision", ""),
                    "components": _pb.get("components", []),
                    "hcodes": _pb.get("hcodes", ""),
                    "vals": dict(_hrec.get("payload", {}).get("vals") or {}),
                    "source": _hrec.get("source", ""),
                    "db_id": _hrec.get("db_id"),
                    "restore": _hrec.get("restore") or {}}
                st.session_state.risk_hist_id = _hrec.get("id")
                st.rerun()
            with open(_RISK_TPL_PATH, "rb") as _tf0:
                hb2.download_button(
                    "⬇️ 엑셀 다운로드 (선택한 이력)",
                    RL.fill_template(_tf0.read(), _hrec.get("payload", {})),
                    file_name=f"화학물질_위험성평가_"
                              f"{_hrec.get('name') or '미입력'}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument."
                         "spreadsheetml.sheet", key="rk_hist_xlsx")
            if hb3.button("🗑 이력 삭제", key="rk_hist_del"):
                _save_risk_db([r for r in _rk_db
                               if r.get("id") != _hsel])
                st.rerun()

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
                st.session_state.risk_score_reset = 0
                st.session_state.risk_hist_id = None
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
        rst = src.get("restore") or {}          # 이력 불러오기 시 위젯 기본값

        def _k(name):
            return f"rk{n}_{name}"

        # ── 빨간 칸 표시 — 직접 입력이 필요하거나 MSDS 판독이 안 된(빈) 항목.
        # 위젯 key에 붙는 st-key-* CSS 클래스로 해당 칸만 붉게 칠한다.
        _red_empty = []

        def _rmark(widget_key, value):
            if value in ("", None, "(선택)"):
                _red_empty.append(widget_key)

        def _rtext(container, label, *args, **kw):
            v = container.text_input(label, *args, **kw)
            _rmark(kw["key"], (v or "").strip())
            return v

        st.markdown(f"##### 🧪 평가 대상: {src.get('name') or '(미입력)'} "
                    f"〔{src.get('source', '')}〕")
        st.caption("🔴 **빨간 칸** = 직접 입력이 필요한 항목 — MSDS에서 자동 "
                   "인식되지 않았거나(판독 실패 포함) 아직 입력·선택하지 않은 "
                   "항목입니다. 값을 채우면 빨간 표시가 사라집니다. "
                   "(②-6 저장 불안정성은 반드시 직접 평가하는 항목이라 항상 "
                   "빨간색으로 표시됩니다.)")

        # ── 1. 기본정보 ──
        st.markdown("###### 1. 평가 대상 화학물질 기본정보")
        c1, c2, c3 = st.columns([1.6, 1.2, 0.9])
        rk_name = _rtext(c1, "제품명 〔MSDS 1항〕", src.get("name", ""),
                         key=_k("name"))
        rk_mf = _rtext(c2, "제조사 〔MSDS 1항〕", src.get("manufacturer", ""),
                       key=_k("mf"))
        rk_rev = _rtext(c3, "MSDS 최신개정일자", src.get("revision", ""),
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
        rk_dept = _rtext(c1, "취급부서 / 공정", rst.get("dept", ""),
                         key=_k("dept"))
        rk_store = _rtext(c2, "저장·보관(예정) 장소", rst.get("store", ""),
                          key=_k("store"))
        rk_purpose = _rtext(c3, "도입 배경 or 목적", rst.get("purpose", ""),
                            key=_k("purpose"))
        rk_hcodes = _rtext(
            st, "★ H-Code (유해위험문구) 〔MSDS 2항 — 자동 인식, 수정 가능〕",
            src.get("hcodes", ""), key=_k("hcodes"),
            help="쉼표/공백으로 구분. H340·H350·H360은 구분까지 표기 "
                 "(예: H350 Cat1A). H314는 MSDS에 1A/1B 명기가 없으면 "
                 "원문대로 H314만 표기하며 구분1로 산정합니다.")

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
                        rk_vals[key] = _rtext(
                            st, full, auto, key=_k(key), placeholder="없음",
                            help=f"MSDS {sec} — 숫자만 입력, 없으면 비워두세요"
                                 + (" (자동 인식됨)" if auto else ""))

        refs = RL.ref_scores(rk_vals)

        # ── 3. 분야별 평가 (②③④) ──
        st.markdown("###### 3. 분야별 위험성평가 — **[참고값]은 자동 계산**되며 "
                    "유해성 점수는 참고값과 동일하게 미리 채워집니다 "
                    "(다르게 평가하면 비고에 사유 기재)")
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
            _pc_rst = (rst.get("poss_common") or [None, None])[i]
            sel = cc[i].selectbox(plabel, range(len(disp)),
                                  index=(_pc_rst + 1) if _pc_rst is not None
                                  else 0,
                                  format_func=lambda x, d=disp: d[x],
                                  key=_k(f"pc_{i}"))
            _rmark(_k(f"pc_{i}"), None if sel == 0 else sel)
            common_poss.append(sel - 1 if sel > 0 else None)

        sheets_payload = {}
        summary_rows = []
        for skey, meta in RL.SHEETS.items():
            with st.expander(f"{meta['title']}", expanded=False):
                scores, notes = [], []
                rst_sc = (rst.get("scores") or {}).get(skey) or []
                rst_nt = (rst.get("notes") or {}).get(skey) or []
                for i, (grp, item) in enumerate(meta["items"]):
                    r = refs[skey][i]
                    a, b, c, dcol = st.columns([2.4, 0.7, 0.8, 1.6])
                    a.markdown(f"**{i + 1}. [{grp}]** {item}")
                    if skey == "2" and i == 5:    # 저장 불안정성 — 직접 평가
                        a.caption(f"ℹ️ {RL.STORE_NOTE}  \n{RL.STORE_CRITERIA}")
                    b.markdown(f"참고값(자동): **{r if r else '—'}**")
                    default_sc = (rst_sc[i] if i < len(rst_sc) and rst_sc[i]
                                  else r or 1)
                    sc = c.selectbox("유해성 점수", [1, 2, 3, 4, 5],
                                     index=default_sc - 1,
                                     key=_k(f"{skey}s{rn}_{i}"),
                                     label_visibility="collapsed")
                    if skey == "2" and i == 5:   # 저장 불안정성 — 상시 빨간 칸
                        _red_empty.append(_k(f"{skey}s{rn}_{i}"))
                    note = dcol.text_input(
                        "비고", rst_nt[i] if i < len(rst_nt) else "",
                        key=_k(f"{skey}note_{i}"),
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
                _pe_rst = (rst.get("poss_env") or {}).get(skey)
                sel = st.selectbox(meta["poss_labels"][2],
                                   range(len(disp)),
                                   index=(_pe_rst + 1)
                                   if _pe_rst is not None else 0,
                                   format_func=lambda x, d=disp: d[x],
                                   key=_k(f"{skey}p_2"))
                _rmark(_k(f"{skey}p_2"), None if sel == 0 else sel)
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
                    _mit_rst = [no for no in ((rst.get("mit") or {})
                                              .get(skey, {}).get(tier) or [])
                                if no in opts]
                    mit[tier] = mcols[ti].multiselect(
                        tlabel, opts, default=_mit_rst,
                        key=_k(f"{skey}m_{tier}"),
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
                if sres["score_missing"]:
                    st.warning(f"유해성 점수 미선택 {sres['score_missing']}건 "
                               "— [참고값(자동)]을 확인하고 항목별 점수를 직접 "
                               "선택해 주세요 (미선택 항목은 0점으로 계산되어 "
                               "위험도가 낮게 나옵니다).")
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
                    if (sh["scores"][i] or 0) >= 4:
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
        _meta_rst = rst.get("meta") or {}
        try:
            _dt_rst = datetime.date.fromisoformat(
                _meta_rst.get("ev_date") or "")
        except ValueError:
            _dt_rst = None
        c1, c2, c3, c4 = st.columns(4)
        ev_type = _rtext(c1, "평가유형", _meta_rst.get("ev_type", ""),
                         key=_k("evtype"), placeholder="예: 신규 도입")
        ev_date = c2.date_input("평가일자", value=_dt_rst, key=_k("evdate"),
                                format="YYYY-MM-DD")
        _rmark(_k("evdate"), ev_date)
        ev_dept = _rtext(c3, "평가부서", _meta_rst.get("ev_dept", ""),
                         key=_k("evdept"))
        ev_by = _rtext(c4, "평가자", _meta_rst.get("ev_by", ""),
                       key=_k("evby"))
        opinion = st.text_area("[기안] 평가자 의견",
                               _meta_rst.get("opinion", ""),
                               key=_k("opinion"), height=80)
        _rmark(_k("opinion"), opinion.strip())

        # 빈 항목 빨간 칸 표시 — 위젯 key의 st-key-* 클래스로 지목
        if _red_empty:
            _sels = ",\n".join(
                f'.st-key-{k} :is('
                'div[data-testid="stTextInputRootElement"],'
                'div[data-testid="stTextAreaRootElement"],'
                '[class*="react-aria-ComboBox"]>div,'
                'div[data-baseweb="input"])'
                for k in _red_empty)
            st.markdown("<style>" + _sels +
                        "{background:#fff1f1 !important;"
                        "border:1px solid #e05555 !important;}\n" +
                        ",\n".join(f".st-key-{k} input, .st-key-{k} textarea"
                                    for k in _red_empty) +
                        "{background:transparent !important;}</style>",
                        unsafe_allow_html=True)

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

        def _mark_risk_done(db_id=src.get("db_id")):
            """등록된 화학물질에서 시작한 평가 → 다운로드 시 완료 표시."""
            if not db_id:
                return
            db2 = _load_review_db()
            for r in db2:
                if r.get("id") == db_id:
                    r["risk_done"] = str(datetime.date.today())
            _save_review_db(db2)

        st.download_button(
            "⬇️ 위험성평가 엑셀 다운로드 (양식 자동 작성)",
            RL.fill_template(_tpl, payload),
            file_name=f"화학물질_위험성평가_{rk_name.strip() or '미입력'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary",
            on_click=_mark_risk_done,
            help="첨부 양식과 동일한 수식·서식의 엑셀 파일에 입력값이 자동 "
                 "기입됩니다. 엑셀에서 열면 수식이 재계산되어 화면과 동일한 "
                 "결과가 표시됩니다."
                 + (" 다운로드하면 등록된 화학물질 조회 목록에 '위험성평가 "
                    "완료'로 표시됩니다." if src.get("db_id") else ""))

        # ── 작성 완료 · 저장 · 초기화 ──
        def _hist_save(status):
            """현재 작성 내용을 위험성평가 이력에 저장(같은 이력이면 갱신)."""
            db = _load_risk_db()
            finals = [result["sheets"][k]["final_risk"] for k in RL.SHEETS]
            entry = {
                "status": status,
                "saved_at": datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M"),
                "name": rk_name.strip(), "source": src.get("source", ""),
                "db_id": src.get("db_id"),
                "verdict": result["verdict"].split("\n")[0],
                "max_risk": max(finals),
                "payload": payload,
                "restore": {
                    "dept": rk_dept.strip(), "store": rk_store.strip(),
                    "purpose": rk_purpose.strip(),
                    "scores": {k: sheets_payload[k]["scores"]
                               for k in sheets_payload},
                    "notes": {k: sheets_payload[k]["notes"]
                              for k in sheets_payload},
                    "poss_common": common_poss,
                    "poss_env": {k: sheets_payload[k]["poss"][2]
                                 for k in sheets_payload},
                    "mit": {k: sheets_payload[k]["mit"]
                            for k in sheets_payload},
                    "meta": dict(payload["meta"])}}
            hid = st.session_state.get("risk_hist_id")
            rec = next((r for r in db if r.get("id") == hid), None)
            if rec is not None:
                entry["id"] = hid
                db[db.index(rec)] = entry
            else:
                entry["id"] = max([r.get("id", 0) for r in db] or [0]) + 1
                db.append(entry)
                st.session_state.risk_hist_id = entry["id"]
            _save_risk_db(db)
            return entry["id"]

        st.divider()
        fb1, fb2, fb3 = st.columns([1.3, 1.3, 1.1])
        if fb1.button("✅ 위험성평가 작성 완료", key=_k("done_btn"),
                      type="primary",
                      help="이력에 '완료'로 저장되고, 등록된 화학물질에서 "
                           "시작한 평가는 조회 목록에 '위험성평가 완료'로 "
                           "표시됩니다."):
            _hid = _hist_save("완료")
            _mark_risk_done()
            st.success(f"작성 완료 — 이력 No.{_hid}에 저장했습니다. "
                       "위 「위험성평가 이력 조회」에서 다시 열거나 엑셀로 "
                       "내려받을 수 있습니다.")
        if fb2.button("💾 저장 (작성중으로 보관)", key=_k("save_btn"),
                      help="작성 중인 내용을 이력에 '작성중'으로 보관합니다. "
                           "「이력 조회 → 불러오기」로 이어서 작성할 수 "
                           "있습니다."):
            _hid = _hist_save("작성중")
            st.info(f"저장했습니다 (이력 No.{_hid}, 작성중). 이력 조회에서 "
                    "불러와 이어서 작성하세요.")
        if fb3.button("🧹 현재 페이지 내용 초기화", key=_k("reset_btn"),
                      help="저장하지 않은 내용은 사라집니다."):
            for _sk in ("risk_src", "risk_up_done", "risk_hist_id"):
                st.session_state.pop(_sk, None)
            st.session_state.risk_nonce = \
                st.session_state.get("risk_nonce", 0) + 1
            st.rerun()

if menu == M_SIGN:
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

# ── 📑 도급신고 ─────────────────────────────────────────────────────────
def _contract_xlsx(db) -> bytes:
    """도급신고 업체 내역을 엑셀로 만든다 (만료임박·만료 컬러마킹)."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    thin = Border(*[Side(style="thin")] * 4)
    mark = {"만료임박": PatternFill("solid", fgColor="FFC7CE"),
            "만료": PatternFill("solid", fgColor="D9D9D9")}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "도급신고 업체 내역"
    headers = ["No.", "업체명", "계약종류", "계약기간", "도급기간",
               "도급 만료까지", "상태", "취급시설", "취급물질",
               "수리공문(환경청)", "등록일"]
    ws.append(headers)
    for c in ws[1]:
        c.fill = PatternFill("solid", fgColor="DDEBF7")
        c.font = Font(bold=True)
        c.border = thin
        c.alignment = Alignment(horizontal="center", vertical="center")
    for r in db:
        d = _ct_days_left(r)
        ws.append([r.get("id"), r.get("company", ""), r.get("ctype", ""),
                   _ct_period(r.get("cont_start"), r.get("cont_end")),
                   _ct_period(r.get("dogub_start"), r.get("dogub_end")),
                   ("" if d is None else
                    (f"D-{d}" if d >= 0 else f"{-d}일 경과")),
                   _ct_status(d), r.get("facility", ""),
                   r.get("substance", ""), r.get("doc_name", ""),
                   r.get("saved_at", "")])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.border = thin
            c.alignment = Alignment(vertical="center", wrap_text=True)
            if c.value in mark:
                c.fill = mark[c.value]
                c.font = Font(bold=True)
    for i, w in enumerate([6, 22, 12, 24, 24, 12, 10, 24, 24, 26, 12], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


if menu == M_CONTRACT:
    st.markdown("도급(하도급) 업체의 **업체명·계약기간·도급기간·취급시설·"
                "취급물질·계약종류·수리공문**을 등록해 도급신고 내역을 누적 "
                "관리합니다. **도급기간 만료일이 1개월 이내로 남으면** 이 "
                "메뉴와 대시보드에 알람이 표시됩니다. 수리공문은 환경청으로부터 "
                "받은 공문 파일을 첨부해 보관합니다.")

    ct_db = _load_contract_db()
    _imm = [(r, d) for r in ct_db
            if _ct_status(d := _ct_days_left(r)) == "만료임박"]
    _exp = [(r, d) for r in ct_db
            if _ct_status(d := _ct_days_left(r)) == "만료"]
    if _imm:
        st.error("🔔 **도급기간 만료 1개월 이내 업체 "
                 f"{len(_imm)}곳** — " +
                 ", ".join(f"{r.get('company', '')}"
                           f"(만료 {r.get('dogub_end', '')}, D-{d})"
                           for r, d in _imm) +
                 " · 재계약 또는 도급신고 갱신이 필요합니다.")
    if _exp:
        st.warning("⏰ 도급기간이 만료된 업체 — " +
                   ", ".join(f"{r.get('company', '')}"
                             f"(만료 {r.get('dogub_end', '')})"
                             for r, d in _exp))

    # ── 등록 ──
    st.markdown("###### 📝 도급신고 등록")
    ctn = st.session_state.get("ct_nonce", 0)

    def _ck(name):
        return f"ct{ctn}_{name}"

    c1, c2 = st.columns([1.4, 1])
    ct_company = c1.text_input("업체명", key=_ck("company"))
    ct_type = c2.selectbox("계약종류", CT_TYPES, key=_ck("type"))
    _ct_opts = _load_ct_opts()
    f1, f2 = st.columns(2)
    ct_fac_sel = f1.multiselect(
        "취급시설 (여러 개 선택 가능)",
        CT_FACILITIES + _ct_opts["facilities"], key=_ck("fac"))
    ct_sub_sel = f2.multiselect(
        "취급물질 (여러 개 선택 가능)",
        CT_SUBSTANCES + _ct_opts["substances"], key=_ck("sub"))
    a1, a2, a3, a4 = st.columns([1.4, 0.6, 1.4, 0.6])
    _new_fac = a1.text_input("목록에 없는 시설 직접 추가", key="ct_new_fac",
                             placeholder="예: 폐수처리장")
    a2.markdown("<div style='height:1.75em'></div>", unsafe_allow_html=True)
    if a2.button("➕ 시설 추가", key="ct_add_fac"):
        v = _new_fac.strip()
        if not v:
            st.warning("추가할 시설명을 입력해 주세요.")
        elif v in CT_FACILITIES + _ct_opts["facilities"]:
            st.info(f"「{v}」은(는) 이미 목록에 있습니다.")
        else:
            _ct_opts["facilities"].append(v)
            _save_ct_opts(_ct_opts)
            st.success(f"취급시설 목록에 「{v}」을(를) 추가했습니다 — 위에서 "
                       "선택하세요.")
            st.rerun()
    _new_sub = a3.text_input("목록에 없는 물질 직접 추가", key="ct_new_sub",
                             placeholder="예: 차아염소산나트륨")
    a4.markdown("<div style='height:1.75em'></div>", unsafe_allow_html=True)
    if a4.button("➕ 물질 추가", key="ct_add_sub"):
        v = _new_sub.strip()
        if not v:
            st.warning("추가할 물질명을 입력해 주세요.")
        elif v in CT_SUBSTANCES + _ct_opts["substances"]:
            st.info(f"「{v}」은(는) 이미 목록에 있습니다.")
        else:
            _ct_opts["substances"].append(v)
            _save_ct_opts(_ct_opts)
            st.success(f"취급물질 목록에 「{v}」을(를) 추가했습니다 — 위에서 "
                       "선택하세요.")
            st.rerun()
    p1, p2, p3, p4 = st.columns(4)
    ct_cs = p1.date_input("계약기간 시작", value=None, key=_ck("cs"),
                          format="YYYY-MM-DD")
    ct_ce = p2.date_input("계약기간 종료", value=None, key=_ck("ce"),
                          format="YYYY-MM-DD")
    ct_ds = p3.date_input("도급기간 시작", value=None, key=_ck("ds"),
                          format="YYYY-MM-DD")
    ct_de = p4.date_input("도급기간 종료 (만료일 — 알람 기준)", value=None,
                          key=_ck("de"), format="YYYY-MM-DD",
                          help="만료일이 1개월 이내로 남으면 이 메뉴와 "
                               "대시보드에 알람이 표시됩니다.")
    ct_doc = st.file_uploader("수리공문 첨부 — 환경청으로부터 받은 공문 파일 "
                              "(PDF·한글·이미지 등, 최대 10MB)",
                              key=_ck("doc"))
    if st.button("💾 도급신고 등록", type="primary", key=_ck("save")):
        if not ct_company.strip():
            st.error("업체명을 입력해 주세요.")
        elif ct_de is None:
            st.error("도급기간 종료일(만료일)을 입력해 주세요 — 만료 알람의 "
                     "기준일입니다.")
        elif ct_doc is not None and ct_doc.size > 10 * 1024 * 1024:
            st.error("수리공문 파일이 10MB를 넘습니다 — 더 작은 파일로 "
                     "첨부해 주세요.")
        else:
            import base64 as _b64
            ct_db.append({
                "id": max([r.get("id", 0) for r in ct_db] or [0]) + 1,
                "company": ct_company.strip(), "ctype": ct_type,
                "facility": ", ".join(ct_fac_sel),
                "substance": ", ".join(ct_sub_sel),
                "cont_start": str(ct_cs) if ct_cs else "",
                "cont_end": str(ct_ce) if ct_ce else "",
                "dogub_start": str(ct_ds) if ct_ds else "",
                "dogub_end": str(ct_de),
                "doc_name": ct_doc.name if ct_doc else "",
                "doc_b64": (_b64.b64encode(ct_doc.getvalue()).decode()
                            if ct_doc else ""),
                "saved_at": str(datetime.date.today())})
            _save_contract_db(ct_db)
            st.session_state.ct_nonce = ctn + 1
            st.session_state.ct_msg = (f"「{ct_company.strip()}」 도급신고를 "
                                       f"등록했습니다. (누적 {len(ct_db)}건)")
            st.rerun()
    if st.session_state.get("ct_msg"):
        st.success(st.session_state.pop("ct_msg"))

    # ── 업체 내역 조회 ──
    st.divider()
    st.markdown(f"###### 📑 도급신고 업체 내역 ({len(ct_db)}건)")
    q1, q2 = st.columns([2.4, 1.6])
    ct_q = q1.text_input("업체명·취급시설·취급물질로 검색", key="ct_q")
    q2.markdown("<div style='height:1.75em'></div>", unsafe_allow_html=True)
    ct_imm_only = q2.checkbox("도급기간 만료 1개월 이내 업체만 보기",
                              key="ct_imm_only")
    _q = ct_q.strip().lower()

    def _ct_hit(r):
        d = _ct_days_left(r)
        if ct_imm_only and _ct_status(d) != "만료임박":
            return False
        if not _q:
            return True
        blob = " ".join([r.get("company", ""), r.get("facility", ""),
                         r.get("substance", ""),
                         r.get("ctype", "")]).lower()
        return _q in blob

    ct_shown = [r for r in ct_db if _ct_hit(r)]
    if ct_shown:
        st.dataframe(
            [{"No.": r.get("id"), "업체명": r.get("company", ""),
              "계약종류": r.get("ctype", ""),
              "계약기간": _ct_period(r.get("cont_start"), r.get("cont_end")),
              "도급기간": _ct_period(r.get("dogub_start"),
                                     r.get("dogub_end")),
              "도급 만료까지": ("" if (d := _ct_days_left(r)) is None else
                               (f"D-{d}" if d >= 0 else f"{-d}일 경과")),
              "상태": _ct_status(_ct_days_left(r)),
              "취급시설": r.get("facility", ""),
              "취급물질": r.get("substance", ""),
              "수리공문": r.get("doc_name", "") or "(없음)",
              "등록일": r.get("saved_at", "")} for r in ct_shown],
            hide_index=True, use_container_width=True)
        st.caption("상태: 정상 = 만료까지 1개월 초과 · **만료임박** = "
                   "1개월(30일) 이내 · 만료 = 도급기간 경과")
        s1, s2, s3 = st.columns([1.2, 1.6, 1.2])
        ct_sel = s1.selectbox(
            "업체 선택 (No.)", [r.get("id") for r in ct_shown],
            format_func=lambda i: next(
                (f"{i} — {r.get('company', '')}" for r in ct_shown
                 if r.get("id") == i), str(i)), key="ct_sel")
        _crec = next((r for r in ct_shown if r.get("id") == ct_sel), None)
        if _crec is not None and _crec.get("doc_b64"):
            import base64 as _b64
            s2.download_button(
                f"📎 수리공문 내려받기 — {_crec.get('doc_name', '')}",
                _b64.b64decode(_crec["doc_b64"]),
                file_name=_crec.get("doc_name") or "수리공문",
                key="ct_doc_dl")
        else:
            s2.caption("선택한 업체에 첨부된 수리공문이 없습니다 — 아래에서 "
                       "추가로 첨부할 수 있습니다.")
        if s3.button("🗑 선택한 등록 삭제", key="ct_del"):
            _save_contract_db([r for r in ct_db if r.get("id") != ct_sel])
            st.rerun()
        # 등록 후 수리공문 추가 첨부 — 공문이 없는 업체에 나중에 붙인다
        if _crec is not None and not _crec.get("doc_b64"):
            late = st.file_uploader(
                f"수리공문 추가 첨부 — {_crec.get('company', '')} "
                "(환경청 공문, 최대 10MB)", key=f"ct_late_{ct_sel}")
            if late is not None and st.button(
                    "📎 선택한 업체에 수리공문 첨부 저장",
                    key=f"ct_late_btn_{ct_sel}", type="primary"):
                if late.size > 10 * 1024 * 1024:
                    st.error("수리공문 파일이 10MB를 넘습니다 — 더 작은 "
                             "파일로 첨부해 주세요.")
                else:
                    import base64 as _b64
                    for r in ct_db:
                        if r.get("id") == ct_sel:
                            r["doc_name"] = late.name
                            r["doc_b64"] = _b64.b64encode(
                                late.getvalue()).decode()
                    _save_contract_db(ct_db)
                    st.session_state.ct_msg = (
                        f"「{_crec.get('company', '')}」에 수리공문 "
                        f"「{late.name}」을(를) 첨부했습니다.")
                    st.rerun()
    else:
        st.caption("등록된 도급신고 업체가 없습니다."
                   if not (_q or ct_imm_only) else "검색 결과가 없습니다.")
    if ct_db:
        st.download_button(
            "⬇️ 엑셀로 내려받기 (도급신고 업체 내역)",
            _contract_xlsx(ct_db),
            file_name="도급신고_업체내역.xlsx",
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", key="ct_xlsx")
