# -*- coding: utf-8 -*-
"""화학물질 위험성평가 — 기준 데이터·점수 산정 로직·엑셀 양식 자동 기입.

「화학물질 위험성평가 Tool」 엑셀 양식(assets/risk_template.xlsx)의 수식을
그대로 포팅했다. 내보낸 엑셀 파일은 자체 수식으로 다시 계산하므로, 화면에
표시하는 값이 엑셀과 일치하도록 양식의 수식을 문자 그대로(엑셀의
텍스트>숫자 비교 규칙 포함) 구현한다. 기준 데이터(저감대책 DB·가능성 옵션·
H코드 점수표)는 양식의 「⑥ 저감대책DB」·「(수정금지) 기준정보」 시트에서
추출한 것이다.
"""
import re
import zipfile
from io import BytesIO

# ── ⑥ 저감대책 DB ────────────────────────────────────────────────────────
RISK_DB = [
 {"no": "PC-E-01", "field": "물리화학", "tier": "공학", "reduce": -3, "text": "완전밀폐 자동화 시스템 (원격취급·로봇·자동공급)", "target": "전 항목 — 노출 경로 자체 차단"},
 {"no": "PC-E-02", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "부분 밀폐 시스템 (Glove box, Closed hood)", "target": "전 항목 — 작업자 접근 차단"},
 {"no": "PC-E-03", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "불활성가스(N₂/Ar) 봉입 저장·취급 시스템", "target": "②자연발화, ⑤폭발·급분해 고위험 시 효과적"},
 {"no": "PC-E-04", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "방폭전기설비 설치 (Zone 0/1/2 분류 준수)", "target": "⑦인화성, ⑧폭발성 고위험 시 효과적"},
 {"no": "PC-E-05", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "자동 온도제어·냉장 보관 시스템", "target": "②자연발화, ⑥저장 불안정 고위험 시 효과적"},
 {"no": "PC-E-06", "field": "물리화학", "tier": "공학", "reduce": -1, "text": "정전기 방지 (접지·본딩·전도성 바닥)", "target": "⑦인화성, ⑧폭발성 보조 대책"},
 {"no": "PC-E-07", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "화재감지·자동소화 시스템 (포·CO₂·하론대체제)", "target": "⑦인화성, ⑧폭발성 고위험 시 효과적"},
 {"no": "PC-E-08", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "폭발방지 설계 (Rupture disc, PSV, 폭압방산구)", "target": "⑤폭발·급분해, ⑧산화성 고위험 시 효과적"},
 {"no": "PC-E-09", "field": "물리화학", "tier": "공학", "reduce": -1, "text": "누액감지 센서 + 방류벽/방지턱(트렌치)", "target": "전 항목 — 누액 사고 방지"},
 {"no": "PC-E-10", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "자동 혼합 통제 인터록 (금기물질 자동 차단)", "target": "③혼합 위험 반응성 고위험 시 효과적"},
 {"no": "PC-E-11", "field": "물리화학", "tier": "공학", "reduce": -2, "text": "가스 감지기 + 비상 셧다운 (LEL/UEL 감지)", "target": "④부산물, ⑦인화성 고위험 시 효과적"},
 {"no": "PC-E-12", "field": "물리화학", "tier": "공학", "reduce": -1, "text": "충격·마찰 방지 용기·운반 (탄성소재·완충재)", "target": "⑤폭발·급분해 보조 대책"},
 {"no": "PC-O-01", "field": "물리화학", "tier": "운영", "reduce": -2, "text": "1회 취급량 최소화", "target": "전 항목 — 노출량 자체 감소"},
 {"no": "PC-O-02", "field": "물리화학", "tier": "운영", "reduce": -2, "text": "1일 취급 시간·횟수 제한", "target": "전 항목 — 노출 빈도 감소"},
 {"no": "PC-O-03", "field": "물리화학", "tier": "운영", "reduce": -2, "text": "저온·저압 조건 운영 (반응성 억제)", "target": "②자연발화, ⑤폭발 보조 대책"},
 {"no": "PC-O-04", "field": "물리화학", "tier": "운영", "reduce": -2, "text": "호환물질 분리 보관 (산·염기·산화제·금수성)", "target": "①물반응, ③혼합금기 고위험 시 효과적"},
 {"no": "PC-O-05", "field": "물리화학", "tier": "운영", "reduce": -1, "text": "과산화물·중합억제제 정기점검 (분해도 측정)", "target": "⑥저장 불안정 보조 대책"},
 {"no": "PC-O-06", "field": "물리화학", "tier": "운영", "reduce": -1, "text": "빈 용기 즉시 처리·환기 (잔류증기 제거)", "target": "⑦인화성 보조 대책"},
 {"no": "PC-O-07", "field": "물리화학", "tier": "운영", "reduce": -1, "text": "재고관리 (선입선출, 유효기간 준수)", "target": "⑥저장 불안정 보조 대책"},
 {"no": "PC-A-01", "field": "물리화학", "tier": "행정", "reduce": -2, "text": "화기작업 허가제 (Hot Work Permit)", "target": "⑦인화성, ⑧폭발성 고위험 시 효과적"},
 {"no": "PC-A-02", "field": "물리화학", "tier": "행정", "reduce": -2, "text": "표준작업절차서(SOP) 수립·게시·준수", "target": "전 항목 — 작업 표준화"},
 {"no": "PC-A-03", "field": "물리화학", "tier": "행정", "reduce": -1, "text": "화학물질 안전보건교육 (MSDS·취급법)", "target": "전 항목 — 작업자 인식 강화"},
 {"no": "PC-A-04", "field": "물리화학", "tier": "행정", "reduce": -1, "text": "비상대응 훈련 (누출·화재·폭발 시나리오)", "target": "④부산물, ⑦인화성, ⑧폭발성"},
 {"no": "PC-A-05", "field": "물리화학", "tier": "행정", "reduce": -1, "text": "MSDS 게시·라벨링·H코드 표시", "target": "전 항목 — 정보 가시화"},
 {"no": "PC-A-06", "field": "물리화학", "tier": "행정", "reduce": -1, "text": "도급사·협력업체 안전관리 협의체 운영", "target": "전 항목 — 다자간 안전 협의"},
 {"no": "PC-P-01", "field": "물리화학", "tier": "보호구", "reduce": -1, "text": "방염·방화복 + 안전화 + 보안경 (화재·열기 노출)", "target": "④부산물, ⑦인화성, ⑧폭발성"},
 {"no": "PC-P-02", "field": "물리화학", "tier": "보호구", "reduce": -1, "text": "화학용 장갑 (재질별: 니트릴·네오프렌·부틸)", "target": "①물반응, ③혼합금기"},
 {"no": "PC-P-03", "field": "물리화학", "tier": "보호구", "reduce": -1, "text": "방폭 공구·정전기 방지 작업복", "target": "⑦인화성, ⑧폭발성"},
 {"no": "EN-E-01", "field": "환경", "tier": "공학", "reduce": -3, "text": "폐쇄형 공정(Closed-loop) — 무방류 시스템", "target": "전 항목 — 배출 자체 제거"},
 {"no": "EN-E-02", "field": "환경", "tier": "공학", "reduce": -2, "text": "폐수처리시설 (활성탄, 응집, 생물처리 등)", "target": "①수생급성, ②수생만성 고위험 시 효과적"},
 {"no": "EN-E-03", "field": "환경", "tier": "공학", "reduce": -2, "text": "VOC 회수·소각 시설 (RTO·RCO·활성탄흡착 등)", "target": "⑧대기·VOC 고위험 시 효과적"},
 {"no": "EN-E-04", "field": "환경", "tier": "공학", "reduce": -2, "text": "대기오염방지시설 — 스크러버 등", "target": "⑧대기 고위험 시 효과적"},
 {"no": "EN-E-05", "field": "환경", "tier": "공학", "reduce": -2, "text": "방류조 + 누유 감지 시스템", "target": "①수생급성, ④토양이동 고위험 시 효과적"},
 {"no": "EN-E-06", "field": "환경", "tier": "공학", "reduce": -2, "text": "토양 보호 (콘크리트 방수바닥, 집수정)", "target": "④토양이동, ⑤토양잔류 고위험 시 효과적"},
 {"no": "EN-E-07", "field": "환경", "tier": "공학", "reduce": -2, "text": "누출감지 시스템 + 비상차단밸브", "target": "①수생급성, ④토양이동"},
 {"no": "EN-E-08", "field": "환경", "tier": "공학", "reduce": -1, "text": "대기·수질 자동측정시스템(TMS)", "target": "⑧대기 모니터링 보조"},
 {"no": "EN-E-09", "field": "환경", "tier": "공학", "reduce": -1, "text": "우수·오폐수 분리 배수 시스템", "target": "①수생급성, ②수생만성"},
 {"no": "EN-E-10", "field": "환경", "tier": "공학", "reduce": -1, "text": "밀폐 펌프·이송 시스템 (Diaphragm·Magnetic-drive)", "target": "①수생급성, ⑧대기"},
 {"no": "EN-E-11", "field": "환경", "tier": "공학", "reduce": -1, "text": "폐기물 보관시설 (지정폐기물 보관기준 준수)", "target": "④토양이동, ⑤토양잔류"},
 {"no": "EN-E-12", "field": "환경", "tier": "공학", "reduce": -1, "text": "환기 및 후드를 통한 대기 배출 최소화", "target": "⑧대기 보조 대책"},
 {"no": "EN-E-13", "field": "환경", "tier": "공학", "reduce": -1, "text": "옥내 보관·옥내 작업 (옥외 풍화 방지)", "target": "④토양이동, ⑤토양잔류, ⑧대기"},
 {"no": "EN-E-14", "field": "환경", "tier": "공학", "reduce": -2, "text": "응급 누출 차단 시스템 (긴급차단밸브·Berm·둑)", "target": "①수생급성, ④토양이동"},
 {"no": "EN-O-01", "field": "환경", "tier": "운영", "reduce": -2, "text": "폐기물 분리보관 → 적정 처리업체 위탁", "target": "③분해성, ⑤토양잔류"},
 {"no": "EN-O-02", "field": "환경", "tier": "운영", "reduce": -1, "text": "세척수·세정수 회수·재사용", "target": "①수생급성, ②수생만성"},
 {"no": "EN-O-03", "field": "환경", "tier": "운영", "reduce": -2, "text": "누출 시 즉시 대응 (Spill Kit·흡착포·중화제)", "target": "①수생급성, ④토양이동"},
 {"no": "EN-O-04", "field": "환경", "tier": "운영", "reduce": -1, "text": "환경친화 세척제·중성 세제 사용", "target": "①수생급성, ②수생만성"},
 {"no": "EN-O-05", "field": "환경", "tier": "운영", "reduce": -2, "text": "취급량 최소화·소분 사용", "target": "전 항목 — 배출량 자체 감소"},
 {"no": "EN-O-06", "field": "환경", "tier": "운영", "reduce": -1, "text": "작업 후 즉시 청소·잔류물 회수", "target": "④토양이동, ⑤토양잔류"},
 {"no": "EN-O-07", "field": "환경", "tier": "운영", "reduce": -1, "text": "야간·우천 시 옥외작업 제한 (빗물 오염 방지)", "target": "①수생급성, ④토양이동"},
 {"no": "EN-A-01", "field": "환경", "tier": "행정", "reduce": -2, "text": "환경관리계획 수립 (배출허가·자가측정)", "target": "전 항목 — 관리 체계 구축"},
 {"no": "EN-A-02", "field": "환경", "tier": "행정", "reduce": -1, "text": "환경교육 (화관법·PBT·VOC·폐기물)", "target": "전 항목 — 작업자 인식 강화"},
 {"no": "EN-A-03", "field": "환경", "tier": "행정", "reduce": -1, "text": "비상누출 대응 매뉴얼·연락체계", "target": "①수생급성, ④토양이동"},
 {"no": "EN-A-04", "field": "환경", "tier": "행정", "reduce": -1, "text": "정기 환경 모니터링·자가측정", "target": "전 항목 — 모니터링 체계"},
 {"no": "EN-A-05", "field": "환경", "tier": "행정", "reduce": -1, "text": "폐기물 최소화 계획 (감량·재이용·재활용)", "target": "③분해성, ⑤토양잔류"},
 {"no": "EN-A-06", "field": "환경", "tier": "행정", "reduce": -1, "text": "친환경 인증 추진 (ISO 14001·에코라벨)", "target": "전 항목 — 시스템 인증"},
 {"no": "EN-A-07", "field": "환경", "tier": "행정", "reduce": -1, "text": "환경영향평가·사전 환경검토", "target": "전 항목 — 사전 검토"},
 {"no": "OH-E-01", "field": "작업자안전", "tier": "공학", "reduce": -3, "text": "완전밀폐 자동화 시스템 (Glovebox·원격취급)", "target": "전 항목 — 노출 경로 완전 차단"},
 {"no": "OH-E-02", "field": "작업자안전", "tier": "공학", "reduce": -2, "text": "국소배기장치(LEV) — 후드·덕트·송풍기", "target": "①흡입독성, ⑦노출기준 고위험 시 효과적"},
 {"no": "OH-E-03", "field": "작업자안전", "tier": "공학", "reduce": -2, "text": "강제 일반환기 (충분한 환기율 확보)", "target": "①흡입독성, ⑦노출기준"},
 {"no": "OH-E-04", "field": "작업자안전", "tier": "공학", "reduce": -2, "text": "글러브박스·격리룸·클린부스 (특별관리물질용)", "target": "①흡입, ②경구·경피, ④발암, ⑧변이원"},
 {"no": "OH-E-05", "field": "작업자안전", "tier": "공학", "reduce": -2, "text": "자동 충진·계량 시스템 (수작업 제거)", "target": "①흡입, ②경구·경피, ③자극·부식"},
 {"no": "OH-E-06", "field": "작업자안전", "tier": "공학", "reduce": -1, "text": "작업환경 실시간 모니터링 (가스검지기 등)", "target": "⑦노출기준 모니터링 보조"},
 {"no": "OH-E-07", "field": "작업자안전", "tier": "공학", "reduce": -1, "text": "비상 샤워·세안기 설치 (10초 이내 접근)", "target": "③자극·부식 보조 대책"},
 {"no": "OH-E-08", "field": "작업자안전", "tier": "공학", "reduce": -1, "text": "진공청소·습식청소 시스템 (분진 비산 방지)", "target": "①흡입, ⑧변이원"},
 {"no": "OH-E-09", "field": "작업자안전", "tier": "공학", "reduce": -2, "text": "송기마스크 공급(Air-line) — 특수작업용", "target": "①흡입, ④발암 고위험 시 효과적"},
 {"no": "OH-E-10", "field": "작업자안전", "tier": "공학", "reduce": -1, "text": "자동 라벨링·바코드 시스템 (오취급 방지)", "target": "전 항목 — 오취급 예방"},
 {"no": "OH-E-11", "field": "작업자안전", "tier": "공학", "reduce": -1, "text": "차폐벽·차폐창 설치 (시각·튐 방지)", "target": "③자극·부식"},
 {"no": "OH-E-12", "field": "작업자안전", "tier": "공학", "reduce": -1, "text": "실외 또는 환기 잘 되는 장소 작업 배치", "target": "①흡입, ⑦노출기준"},
 {"no": "OH-E-13", "field": "작업자안전", "tier": "공학", "reduce": -1, "text": "작업장 출입통제·인터록 시스템", "target": "전 항목 — 비취급자 노출 차단"},
 {"no": "OH-O-01", "field": "작업자안전", "tier": "운영", "reduce": -2, "text": "작업환경측정 정기 실시 (반기 1회·특별관리물질)", "target": "⑦노출기준 — 노출수준 정량 파악"},
 {"no": "OH-O-02", "field": "작업자안전", "tier": "운영", "reduce": -2, "text": "1회 취급량 소분 (소량 다회 분할)", "target": "①흡입, ②경구·경피, ⑦노출기준"},
 {"no": "OH-O-03", "field": "작업자안전", "tier": "운영", "reduce": -2, "text": "노출시간 제한·작업 순환(Job rotation)", "target": "④발암, ⑤생식, ⑦노출기준 — 누적 노출량 제한"},
 {"no": "OH-O-04", "field": "작업자안전", "tier": "운영", "reduce": -1, "text": "식음·흡연·화장 금지 구역 지정", "target": "②경구·경피 — 경구 노출 방지"},
 {"no": "OH-O-05", "field": "작업자안전", "tier": "운영", "reduce": -1, "text": "오염 작업복 분리세탁·격리 (가족 노출 차단)", "target": "②경구·경피, ③자극, ④발암"},
 {"no": "OH-O-06", "field": "작업자안전", "tier": "운영", "reduce": -1, "text": "작업 후 즉시 손·얼굴·신체 세척", "target": "②경구·경피, ③자극"},
 {"no": "OH-O-07", "field": "작업자안전", "tier": "운영", "reduce": -2, "text": "임산부·임신가능 여성 작업 제한 (생식독성 물질)", "target": "⑤생식독성 고위험 시 필수"},
 {"no": "OH-A-01", "field": "작업자안전", "tier": "행정", "reduce": -1, "text": "특수건강진단 (배치전·정기·임시·수시)", "target": "④발암, ⑤생식, ⑥STOT, ⑧변이원 — 건강영향 조기 발견"},
 {"no": "OH-A-02", "field": "작업자안전", "tier": "행정", "reduce": -1, "text": "화학물질 안전보건교육 (MSDS·취급법)", "target": "전 항목 — 작업자 인식 강화"},
 {"no": "OH-A-03", "field": "작업자안전", "tier": "행정", "reduce": -2, "text": "작업허가서(Permit-to-work)", "target": "④발암, ⑦노출기준 — 위험 작업 사전 통제"},
 {"no": "OH-A-04", "field": "작업자안전", "tier": "행정", "reduce": -1, "text": "특별관리물질 등록·취급일지 작성", "target": "④발암, ⑧변이원 — 관리체계 구축"},
 {"no": "OH-A-05", "field": "작업자안전", "tier": "행정", "reduce": -1, "text": "응급의료체계 구축 (해독제·비상연락·구급차)", "target": "①흡입, ②경구·경피, ③자극 — 사고 시 대응"},
 {"no": "OH-A-06", "field": "작업자안전", "tier": "행정", "reduce": -2, "text": "위험성평가 실시 (정기:1년,2년 등, 수시:물질변경 시)", "target": "전 항목 — 평가 갱신"},
 {"no": "OH-P-01", "field": "작업자안전", "tier": "보호구", "reduce": -1, "text": "호흡보호구 (방진·방독·송기 등 등급별)", "target": "①흡입, ⑥STOT·호흡과민"},
 {"no": "OH-P-02", "field": "작업자안전", "tier": "보호구", "reduce": -1, "text": "화학보호복+화학장갑+보안경+안전화", "target": "②경구·경피, ③자극·부식"},
]
RISK_DB_BY_NO = {d["no"]: d for d in RISK_DB}

# ── 가능성 평가 선택지 (기준정보 시트 — 엑셀 VLOOKUP과 정확히 일치해야 함) ──
POSS_FREQ = ["연 1-2회", "연 3-11회", "월 1회 이상", "주 1회 이상", "매일 1회 이상"]
POSS_AMOUNT = ["1회 취급량 1kg(L) 미만", "1회 취급량 1-10kg(L)", "1회 취급량 10-100kg(L)", "1회 취급량 100-1000kg(L)", "1회 취급량 1000kg(L) 이상 또는 대량 상시 취급"]
_ENV = {"2": ["완전 밀폐 공정 내 취급 (직접 개봉 없음)", "밀폐 공간 내 간헐적 계량·분주 작업 (환기 양호)", "부분 개방 환경에서 주기적 취급·이송 (일반 옥내작업, 기본 환기)", "개방 환경·반응 설비에서 반복적 취급 작업", "개방 공정에서 상시 반응·혼합·이송 작업 \n또는 고온·고압·복합 위험 환경"],
        "3": ["밀폐 공정, 수계·토양·대기 배출 경로 없음", "사용 후 즉시 밀봉, 환경 접촉 가능성 낮음 (유사시 즉시 전량 회수 가능)", "주기적 사용, 소량 잔류·배출 또는 대기 휘발 가능 (유사시 외부 누출 가능성 有)", "반복적 사용, 수계·토양 접촉 또는 대기 배출 가능성 상당", "개방 공정, 수계·토양·대기 배출 경로 상시 존재"],
        "4": ["완전 자동화·원격 조작 또는 완전 밀폐 공간 취급", "밀폐 공간·밀폐 용기에서 간헐적 취급, 직접 노출 낮음", "부분 개방 환경에서 주기적 취급, 1일 1-2시간 미만", "개방 환경에서 반복적 취급, 1일 노출 2-4시간", "개방 공정, 1일 직접 노출·취급 시간 4시간 이상"]}

# ── ① 기초Data 입력 항목 선택지 ──────────────────────────────────────────
WATER_REACT_OPTIONS = ["비반응 또는 내용 없음", "미약반응(ΔT<10°C): 약한 발열",
                       "중등반응(ΔT10~50°C): 중간 발열",
                       "격렬반응(ΔT>50°C): 심한 발열"]
DECOMP_OPTIONS = ["없음(CO₂·H₂O)", "저독성·TLV이하", "GHS Cat3~4 자극성",
                  "GHS Cat1~2 독성", "CMR급(다이옥신·HCN 등)"]
IARC_OPTIONS = ["없음", "IARC Group1", "IARC Group2A", "IARC Group2B",
                "IARC Group3"]
PBT_OPTIONS = ["비해당 또는 없음", "PBT 1가지 해당", "PBT 2가지 해당",
               "PBT기준 3가지 해당", "vPvB 해당"]

# (key, ①시트 셀, 항목명, 종류, 단위, MSDS 참조)
RISK_FIELDS = [
    ("twa_mg", "D42", "작업환경 노출기준 TWA", "num", "mg/m³", "8항"),
    ("twa_ppm", "D43", "작업환경 노출기준 TWA", "num", "ppm", "8항"),
    ("flash", "D45", "인화점 (Flash Point)", "num", "°C", "9항"),
    ("boiling", "D46", "끓는점 (Boiling Point)", "num", "°C", "9항"),
    ("ait", "D47", "자연발화온도 (AIT)", "num", "°C", "9항"),
    ("vapor", "D48", "증기압", "num", "mmHg @20°C", "9항"),
    ("logkow", "D49", "logKow (옥탄올/물 분배계수)", "num", "", "9항"),
    ("water_react", "D51", "물과의 반응 정도", "select", "", "10항"),
    ("taboo", "D52", "금기물질 유형 수", "num", "종", "10항"),
    ("decomp_temp", "D53", "분해온도", "num", "°C", "9·10항"),
    ("decomp_prod", "D54", "분해 생성물 독성 수준", "select", "", "10항"),
    ("lc50_vapor", "D56", "흡입독성 LC50 — 증기 (rat, 4h)", "num", "mg/L", "11항"),
    ("lc50_dust", "D57", "흡입독성 LC50 — 분진/미스트 (rat, 4h)", "num", "mg/L",
     "11항"),
    ("ld50_oral", "D58", "경구독성 LD50 (rat)", "num", "mg/kg", "11항"),
    ("ld50_dermal", "D59", "경피독성 LD50", "num", "mg/kg", "11항"),
    ("iarc", "D60", "IARC 발암성 분류", "select", "", "11항"),
    ("fish_lc50", "D62", "수생 어류 LC50 (96h)", "num", "mg/L", "12항"),
    ("daphnia_ec50", "D63", "수생 물벼룩/갑각류 EC50 (48h)", "num", "mg/L", "12항"),
    ("bcf", "D64", "생물농축계수 BCF", "num", "", "12항"),
    ("dt50", "D65", "토양 반감기 DT50 (수계)", "num", "일", "12항"),
    ("biodeg", "D66", "생분해도 (OECD 28일 기준)", "num", "%", "12항"),
    ("koc", "D67", "토양 이동성 (Koc)", "num", "", "12항"),
    ("pbt", "D68", "PBT/vPvB 해당 여부", "select", "", "12항"),
]
SELECT_OPTIONS = {"water_react": WATER_REACT_OPTIONS, "decomp_prod": DECOMP_OPTIONS,
                  "iarc": IARC_OPTIONS, "pbt": PBT_OPTIONS}

# 화면 표시용 그룹 (MSDS 항 순서)
RISK_GROUPS = [
    ("Sec 8 — 노출기준 (TWA)", ["twa_mg", "twa_ppm"]),
    ("Sec 9 — 물리화학적 특성", ["flash", "boiling", "ait", "vapor", "logkow"]),
    ("Sec 10 — 반응성 정성 평가", ["water_react", "taboo", "decomp_temp",
                                   "decomp_prod"]),
    ("Sec 11 — 독성 데이터 (LD50/LC50)", ["lc50_vapor", "lc50_dust",
                                          "ld50_oral", "ld50_dermal", "iarc"]),
    ("Sec 12 — 환경 데이터", ["fish_lc50", "daphnia_ec50", "bcf", "dt50",
                              "biodeg", "koc", "pbt"]),
]
RISK_FIELD_BY_KEY = {f[0]: f for f in RISK_FIELDS}

# ── H-Code → ①시트 D23~D40 자동 판정 (기준정보 코드 목록, 점수 높은 순) ──
AUTO_CODES = [
    ("d23", ["H220", "H222", "H224", "H221", "H223", "H225", "H228", "H226",
             "H227"]),
    ("d24", ["H200", "H201", "H202", "H203", "H204", "H205", "H206", "H240",
             "H207", "H241", "H208", "H242"]),
    ("d25", ["H270", "H271", "H272"]),
    ("d26", ["H260", "H261"]),
    ("d27", ["H290"]),
    ("d28", ["H250", "H251", "H252"]),
    ("d29", ["H330", "H331", "H332"]),
    ("d30", ["H300", "H310", "H301", "H304", "H311", "H305", "H302", "H312"]),
    ("d31", ["H314 Cat1A", "H314 Cat1B", "H314 Cat1", "H315", "H317", "H316"]),
    ("d32", ["H318", "H319", "H320"]),
    ("d33", ["H350 Cat1A", "H350 Cat1B", "H351"]),
    ("d34", ["H360 Cat1A", "H360 Cat1B", "H361", "H362"]),
    ("d35", ["H370", "H371", "H372", "H373"]),
    ("d36", ["H334", "H335", "H336"]),
    ("d37", ["H340 Cat1A", "H340 Cat1B", "H341"]),
    ("d38", ["H400", "H401", "H402"]),
    ("d39", ["H410", "H411", "H412", "H413"]),
    ("d40", ["H420"]),
]
AUTO_LABELS = {
    "d23": "인화성", "d24": "폭발성", "d25": "산화성", "d26": "물 반응성",
    "d27": "금속부식성", "d28": "자연발화·자기발열", "d29": "급성독성 흡입",
    "d30": "급성독성 경구·경피", "d31": "피부 부식성·자극성",
    "d32": "눈 손상·자극성", "d33": "발암성", "d34": "생식독성",
    "d35": "STOT 반복독성", "d36": "호흡기 과민성", "d37": "변이원성",
    "d38": "수생 급성독성", "d39": "수생 만성독성", "d40": "오존층 파괴",
}


def auto_codes(hcodes: str) -> dict:
    """①시트 D23~D40 — H-Code 문자열에서 항목별 해당 코드를 판정한다.

    엑셀 수식(INDEX/MATCH+SEARCH)과 동일하게, 목록 순서(높은 점수 순)대로
    부분 문자열 검색(대소문자 무시)해 처음 발견되는 코드를 쓴다.
    """
    text = (hcodes or "").upper()
    out = {}
    for key, codes in AUTO_CODES:
        out[key] = next((c for c in codes if c.upper() in text), "없음")
    return out


# ── 평가 시트 구성(②③④) ────────────────────────────────────────────────
SHEETS = {
    "2": {
        "title": "② 물리화학적 위험성", "field": "물리화학", "has_ppe": True,
        "poss_labels": ["① 취급 횟수", "② 1회 취급량", "③ 취급 공정 환경"],
        "items": [
            ("반응성", "물·산·염기와의 접촉 반응성 (발열, 가스 발생 등)"),
            ("반응성", "공기·수분 반응·자연발화 (흡습 발열, 자기발화)"),
            ("반응성", "혼합 위험 반응성 (금기물질·혼합금지 성분)"),
            ("부산물", "독성 부산물·분해·연소 생성물"),
            ("불안정성", "폭발·급분해 불안정성 (열·충격·마찰·정전기)"),
            ("불안정성", "저장 불안정성 (과산화물·자발중합·변질)"),
            ("화재", "인화성"),
            ("폭발", "폭발성·산화성")],
        # 고위험(4점↑) 항목별 추천 저감대책 (공학, 운영, 행정, 보호구)
        "rec": [("PC-E-03", "PC-O-04", "PC-A-02", "PC-P-02"),
                ("PC-E-05", "PC-O-03", "PC-A-03", "PC-P-01"),
                ("PC-E-10", "PC-O-04", "PC-A-02", None),
                ("PC-E-11", None, "PC-A-04", "PC-P-01"),
                ("PC-E-08", "PC-O-03", "PC-A-04", "PC-P-01"),
                ("PC-E-05", "PC-O-05", "PC-A-02", None),
                ("PC-E-04", "PC-O-06", "PC-A-01", "PC-P-01"),
                ("PC-E-08", "PC-O-04", "PC-A-01", "PC-P-03"),
                (None, "PC-O-02", "PC-A-02", None),
                (None, "PC-O-01", None, None),
                ("PC-E-01", None, None, None)],
    },
    "3": {
        "title": "③ 환경오염 위험성", "field": "환경", "has_ppe": False,
        "poss_labels": ["① 취급 횟수", "② 1회 취급량", "③ 환경 접촉 가능성"],
        "items": [
            ("수계오염", "수생 생물 급성 독성"),
            ("수계오염", "수생 생물 만성 독성"),
            ("수계오염", "수계 분해성·생분해도"),
            ("토양오염", "토양 흡착성·이동성 (Koc / logKow)"),
            ("토양오염", "토양 잔류성 (반감기 DT50)"),
            ("생물농축", "생물농축성 (BCF 또는 logKow)"),
            ("생물농축", "PBT/vPvB 복합 특성"),
            ("대기오염", "대기오염 영향 (VOC, ODS)")],
        "rec": [("EN-E-02", "EN-O-03", "EN-A-04", None),
                ("EN-E-02", "EN-O-02", "EN-A-05", None),
                ("EN-E-08", "EN-O-01", "EN-A-05", None),
                ("EN-E-05", "EN-O-03", "EN-A-03", None),
                ("EN-E-06", "EN-O-01", "EN-A-05", None),
                ("EN-E-01", "EN-O-05", "EN-A-07", None),
                ("EN-E-01", "EN-O-05", "EN-A-07", None),
                ("EN-E-04", "EN-O-05", "EN-A-01", None),
                (None, "EN-O-05", "EN-A-04", None),
                (None, "EN-O-05", "EN-A-04", None),
                ("EN-E-13", None, None, None)],
    },
    "4": {
        "title": "④ 작업자 안전보건", "field": "작업자안전", "has_ppe": True,
        "poss_labels": ["① 취급 횟수", "② 1회 취급량", "③ 취급 공정 환경"],
        "items": [
            ("급성독성", "흡입 독성 (증기, 분기/미스트)"),
            ("급성독성", "경구·경피 독성"),
            ("급성독성", "피부·눈 자극성 및 부식성"),
            ("만성독성", "발암성"),
            ("만성독성", "생식·발달독성"),
            ("만성독성", "특정 장기 반복독성 및 호흡기 과민성"),
            ("만성독성", "생식세포 변이원성"),
            ("노출기준", "작업환경 노출기준")],
        "rec": [("OH-E-03", "OH-O-01", "OH-A-06", "OH-P-01"),
                ("OH-E-05", "OH-O-04", "OH-A-02", "OH-P-02"),
                ("OH-E-07", "OH-O-06", "OH-A-05", "OH-P-02"),
                ("OH-E-09", "OH-O-03", "OH-A-03", "OH-P-01"),
                ("OH-E-04", "OH-O-07", "OH-A-01", "OH-P-02"),
                ("OH-E-02", "OH-O-01", "OH-A-01", "OH-P-01"),
                ("OH-E-02", "OH-O-01", "OH-A-03", "OH-P-01"),
                ("OH-E-04", "OH-O-03", "OH-A-04", "OH-P-02"),
                (None, "OH-O-03", "OH-A-03", None),
                (None, "OH-O-02", None, None),
                ("OH-E-12", None, None, None)],
    },
}
TIERS = [("eng", "공학적 제어 (Engineering)", "공학"),
         ("op", "운영적 제어 (Operational)", "운영"),
         ("adm", "행정적 제어 (Administrative)", "행정"),
         ("ppe", "보호구(PPE) 착용 의무화", "보호구")]


def poss_options(sheet_key: str):
    return [POSS_FREQ, POSS_AMOUNT, _ENV[sheet_key]]


# ── 숫자 비교 (엑셀 규칙: 텍스트는 어떤 숫자보다 크다) ────────────────────
def _f(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _lt(v, x):
    n = _f(v)
    return n is not None and n < x


def _le(v, x):
    n = _f(v)
    return n is not None and n <= x


def _gt(v, x):
    n = _f(v)
    return n > x if n is not None else True


def _ge(v, x):
    n = _f(v)
    return n >= x if n is not None else True


def _blank(v):
    return str(v or "").strip() in ("", "없음")


def ref_scores(vals: dict) -> dict:
    """②③④ 시트의 [참고값] 유해성(E8~E15)을 양식 수식 그대로 계산한다.

    수동 평가 항목(②-6 저장 불안정성)은 None."""
    d = auto_codes(vals.get("hcodes", ""))
    v = vals

    def water_score():
        if d["d26"] in ("H260", "H261"):
            return 5
        if d["d27"] == "H290":
            return 4
        w = v.get("water_react", "")
        return {WATER_REACT_OPTIONS[3]: 4, WATER_REACT_OPTIONS[2]: 3,
                WATER_REACT_OPTIONS[1]: 2}.get(w, 1)

    taboo = _f(v.get("taboo")) or 0
    s2 = [
        water_score(),
        max({"H250": 5, "H251": 4, "H252": 3}.get(d["d28"], 1),
            5 if _lt(v.get("ait"), 54) else 4 if _lt(v.get("ait"), 100)
            else 3 if _lt(v.get("ait"), 200) else 1),
        4 if taboo >= 5 else 3 if taboo >= 3 else 2 if taboo >= 1 else 1,
        {DECOMP_OPTIONS[4]: 5, DECOMP_OPTIONS[3]: 4, DECOMP_OPTIONS[2]: 3,
         DECOMP_OPTIONS[1]: 2}.get(v.get("decomp_prod", ""), 1),
        max(5 if d["d24"] in ("H200", "H201", "H202", "H203", "H204", "H205")
            else 4 if d["d24"] in ("H206", "H240")
            else 3 if d["d24"] in ("H207", "H241")
            else 2 if d["d24"] in ("H208", "H242") else 1,
            4 if _lt(v.get("decomp_temp"), 100)
            else 3 if _lt(v.get("decomp_temp"), 150)
            else 2 if _lt(v.get("decomp_temp"), 300) else 1),
        None,                                    # ②-6 저장 불안정성(직접 입력)
        max(5 if d["d23"] in ("H220", "H222", "H224")
            else 4 if d["d23"] in ("H221", "H223", "H225", "H228")
            else 3 if d["d23"] == "H226" else 2 if d["d23"] == "H227" else 1,
            1 if _ge(v.get("flash"), 93) else 2 if _ge(v.get("flash"), 60)
            else 3 if _ge(v.get("flash"), 23)
            else 4 if _lt(v.get("flash"), 23) and _gt(v.get("boiling"), 35)
            else 5 if _lt(v.get("flash"), 23) and _le(v.get("boiling"), 35)
            else 1),
        max(5 if d["d24"] in ("H200", "H201", "H202")
            else 4 if d["d24"] in ("H203", "H204", "H205") else 1,
            {"H270": 5, "H271": 4, "H272 Cat2": 3,
             "H272 Cat3": 2}.get(d["d25"], 1)),
    ]

    def aqua(val):
        return (5 if _le(val, 1) else 4 if _le(val, 10) else 3 if _le(val, 100)
                else 2 if _le(val, 1000) else 1)

    def vnum(key, default=None):
        return default if _blank(v.get(key)) else _f(v.get(key))

    dt50, biodeg = vnum("dt50"), vnum("biodeg")
    logkow, koc, bcf = vnum("logkow"), vnum("koc"), vnum("bcf")
    vapor = vnum("vapor")
    pbt = v.get("pbt", "")
    s3 = [
        max({"H400": 5, "H401": 4, "H402": 3}.get(d["d38"], 1),
            aqua(v.get("fish_lc50")), aqua(v.get("daphnia_ec50"))),
        {"H410": 5, "H411": 4, "H412": 3, "H413": 2}.get(d["d39"], 1),
        max(1 if dt50 is None else 5 if dt50 > 180 else 4 if dt50 > 60
            else 3 if dt50 > 28 else 2 if dt50 > 10 else 1,
            1 if biodeg is None else 5 if biodeg < 5 else 4 if biodeg < 20
            else 3 if biodeg < 40 else 2 if biodeg < 60 else 1),
        max(1 if logkow is None else 5 if logkow < 2 else 4 if logkow < 2.7
            else 3 if logkow < 3.5 else 2 if logkow < 4.5 else 1,
            1 if koc is None else 5 if koc < 50 else 4 if koc < 200
            else 3 if koc < 1000 else 2 if koc < 5000 else 1),
        (1 if dt50 is None else 5 if dt50 > 365 else 4 if dt50 > 180
         else 3 if dt50 > 120 else 2 if dt50 > 60 else 1),
        max(5 if pbt == "vPvB 해당" else 4 if pbt == "PBT기준 3가지 해당" else 1,
            1 if bcf is None else 5 if bcf >= 5000 else 4 if bcf >= 2000
            else 3 if bcf >= 500 else 2 if bcf >= 100 else 1,
            1 if logkow is None else 5 if logkow >= 5.2 else 4 if logkow >= 4.7
            else 3 if logkow >= 4 else 2 if logkow >= 3.2 else 1),
        {"vPvB 해당": 5, "PBT기준 3가지 해당": 4, "PBT 2가지 해당": 3,
         "PBT 1가지 해당": 2}.get(pbt, 1),
        max(5 if d["d40"] == "H420" else 1,
            1 if vapor is None else 4 if vapor >= 100 else 3 if vapor >= 10
            else 2 if vapor >= 1 else 1),
    ]

    s4 = [
        max({"H330": 5, "H331": 4, "H332": 3, "H333": 3}.get(d["d29"], 1),
            5 if _le(v.get("lc50_vapor"), 0.5) else 4 if _le(v.get("lc50_vapor"), 2)
            else 3 if _le(v.get("lc50_vapor"), 20)
            else 2 if _le(v.get("lc50_vapor"), 50) else 1,
            5 if _le(v.get("lc50_dust"), 0.5) else 4 if _le(v.get("lc50_dust"), 1)
            else 3 if _le(v.get("lc50_dust"), 5)
            else 2 if _le(v.get("lc50_dust"), 12.5) else 1),
        max(5 if d["d30"] in ("H300", "H310")
            else 4 if d["d30"] in ("H301", "H304", "H311")
            else 3 if d["d30"] == "H305"
            else 2 if d["d30"] in ("H302", "H312") else 1,
            5 if _le(v.get("ld50_oral"), 50) else 4 if _le(v.get("ld50_oral"), 300)
            else 3 if _le(v.get("ld50_oral"), 1000)
            else 2 if _le(v.get("ld50_oral"), 2000) else 1,
            5 if _le(v.get("ld50_dermal"), 200)
            else 4 if _le(v.get("ld50_dermal"), 1000)
            else 3 if _le(v.get("ld50_dermal"), 1500)
            else 2 if _le(v.get("ld50_dermal"), 2000) else 1),
        max(5 if d["d31"] == "H314 Cat1A"
            else 4 if d["d31"] in ("H314 Cat1B", "H314 Cat1")
            else 3 if d["d31"] in ("H315", "H317")
            else 2 if d["d31"] == "H316" else 1,
            {"H318": 4, "H319": 3, "H320": 2}.get(d["d32"], 1)),
        max({"H350 Cat1A": 5, "H350 Cat1B": 4, "H351": 3}.get(d["d33"], 1),
            {"IARC Group1": 5, "IARC Group2A": 4, "IARC Group2B": 3,
             "IARC Group3": 2}.get(v.get("iarc", ""), 1)),
        {"H360 Cat1A": 5, "H360 Cat1B": 4, "H361": 3,
         "H362": 2}.get(d["d34"], 1),
        max({"H370": 5, "H371": 4, "H372": 3, "H373": 2}.get(d["d35"], 1),
            # 양식 수식 그대로("334" 비교) — D36은 "H334" 형태라 항상 1이 된다
            {"334": 4, "335": 3, "336": 2}.get(d["d36"], 1)),
        {"H340 Cat1A": 5, "H340 Cat1B": 4, "H341": 3}.get(d["d37"], 1),
        max(5 if _lt(v.get("twa_mg"), 0.1) else 4 if _lt(v.get("twa_mg"), 1)
            else 3 if _lt(v.get("twa_mg"), 10)
            else 2 if _lt(v.get("twa_mg"), 100) else 1,
            5 if _lt(v.get("twa_ppm"), 0.05) else 4 if _lt(v.get("twa_ppm"), 0.5)
            else 3 if _lt(v.get("twa_ppm"), 5)
            else 2 if _lt(v.get("twa_ppm"), 50) else 1),
    ]
    return {"2": s2, "3": s3, "4": s4}


# ── 등급·위험도 산정 ─────────────────────────────────────────────────────
def hazard_summary(scores) -> dict:
    total = sum(scores)
    mx = max(scores) if scores else 0
    weight = 2 if mx >= 5 else 1 if mx >= 4 else 0
    final = min(40, total + weight)
    grade = (1 if final < 8.5 else 2 if final < 16.5 else 3 if final < 24.5
             else 4 if final < 33.5 else 5)
    fatal = sum(1 for s in scores if s >= 5)
    return {"total": total, "weight": weight, "final": final, "grade": grade,
            "fatal": fatal}


def poss_grade(score) -> int:
    return (1 if score < 3.5 else 2 if score < 6.5 else 3 if score < 9.5
            else 4 if score < 12.5 else 5)


def risk_level(risk) -> str:
    return ("낮음" if risk < 3.5 else "보통" if risk < 8.5
            else "높음" if risk < 16.5 else "매우 높음")


def final_level(risk) -> str:
    return ("저" if risk < 3.5 else "중" if risk < 8.5
            else "고" if risk < 16.5 else "허용 불가")


def _median3(a):
    return sorted(a)[1]


def mitigation_effect(mit: dict, pscore: float, has_ppe: bool) -> dict:
    """저감대책 적용 효과 — 양식 P59~T61 수식 그대로.

    mit: {"eng": [DB No.×3], "op": [...], "adm": [...], "ppe": [...]}"""
    s = {}
    for tier, _, _ in TIERS:
        reds = [RISK_DB_BY_NO.get(no, {}).get("reduce", 0)
                for no in (mit.get(tier) or [])][:3]
        reds += [0] * (3 - len(reds))
        s[tier] = min(reds) * 1 + _median3(reds) * 0.75 + max(reds) * 0.5
    t = s["eng"] * 1 + s["op"] * 0.75 + s["adm"] * 0.5
    if has_ppe:
        t += s["ppe"] * 0.5
    t = max(t, -pscore * 0.6)                    # 전체 감소량 상한 60%
    new_score = max(3, pscore + t)               # 하한 3점
    return {"reduction": t, "new_score": new_score,
            "new_grade": poss_grade(new_score)}


def overall_verdict(final_risks, fatal_total) -> str:
    """⑤ 종합결과 「검토 결과」(D16) 수식 그대로."""
    m = max(final_risks)
    fatal = ("\n🟠 치명항목(유해성 5점) 有  — SHE부서 검토자 반영 필요"
             if fatal_total >= 1 else "")
    if m >= 17:
        return "🔴 허용 불가  — 원칙적 도입/취급 불가 (도입하려면 경영진 예외 승인 필수)"
    if m >= 10:
        return "🟠 고위험  — 저감대책 보강 후 재평가하여 위험도 감소 후 도입/취급 가능"
    if m >= 5:
        return ("🟡 중위험 — 부서장 승인 후 도입/취급 가능 "
                "(추가 저감대책 검토 권장, 모니터링 지속)" + fatal)
    return "🟢 저위험  — 부서장 승인 후 도입/취급 가능" + fatal


def evaluate(vals: dict, sheets: dict) -> dict:
    """전체 평가 계산.

    sheets: {"2": {"scores": [8개 1~5], "poss": [idx|None×3],
                   "mit": {tier: [DB No.]}}, ...}
    """
    refs = ref_scores(vals)
    out = {"refs": refs, "sheets": {}}
    finals, fatal_total = [], 0
    for key, meta in SHEETS.items():
        sh = sheets.get(key, {})
        scores = sh.get("scores") or [r or 1 for r in refs[key]]
        hz = hazard_summary(scores)
        poss_idx = sh.get("poss") or [None, None, None]
        pscore = sum((i + 1) for i in poss_idx if i is not None)
        pg = poss_grade(pscore)
        risk = hz["grade"] * pg
        mit = mitigation_effect(sh.get("mit") or {}, pscore, meta["has_ppe"])
        final_risk = hz["grade"] * mit["new_grade"]
        finals.append(final_risk)
        fatal_total += hz["fatal"]
        out["sheets"][key] = {
            "hazard": hz, "poss_score": pscore, "poss_grade": pg,
            "risk": risk, "level": risk_level(risk), "allow": risk <= 8,
            "mit": mit, "final_risk": final_risk,
            "final_level": final_level(final_risk),
            "final_allow": final_risk <= 8,
            "poss_missing": any(i is None for i in poss_idx),
        }
    out["verdict"] = overall_verdict(finals, fatal_total)
    out["fatal_total"] = fatal_total
    return out


# ── 엑셀 양식 자동 기입 ──────────────────────────────────────────────────
_CELL_RX = {}


def _set_cell(xml: str, ref: str, value, numeric=None) -> str:
    """시트 XML의 셀에 값을 기입한다(스타일 유지, 수식 셀은 건드리지 않음)."""
    if value is None:
        return xml
    sval = str(value).strip()
    if sval == "":
        return xml
    rx = _CELL_RX.get(ref)
    if rx is None:
        rx = _CELL_RX[ref] = re.compile(
            r'<c r="%s"([^>]*?)(?:/>|>.*?</c>)' % re.escape(ref), re.S)
    m = rx.search(xml)
    if not m:
        return xml
    attrs = re.sub(r'\s*t="[^"]*"', "", m.group(1))
    num = _f(sval) if numeric is not False else None
    if num is not None and numeric is not False:
        rep = '<c r="%s"%s><v>%s</v></c>' % (
            ref, attrs, ("%d" % num) if num == int(num) else repr(num))
    else:
        esc = (sval.replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;"))
        rep = ('<c r="%s"%s t="inlineStr"><is>'
               '<t xml:space="preserve">%s</t></is></c>') % (ref, attrs, esc)
    return xml[:m.start()] + rep + xml[m.end():]


def fill_template(template_bytes: bytes, payload: dict) -> bytes:
    """위험성평가 결과를 양식에 기입한 xlsx 바이트를 돌려준다.

    payload: {"basic": {name, manufacturer, revision, components, dept,
                        storage, purpose, hcodes}, "vals": {...RISK_FIELDS},
              "sheets": {"2": {"scores", "notes", "poss", "mit"}, ...},
              "meta": {ev_type, ev_date, ev_dept, ev_by, opinion}}
    """
    basic = payload.get("basic", {})
    vals = payload.get("vals", {})
    sheets = payload.get("sheets", {})
    meta = payload.get("meta", {})

    zin = zipfile.ZipFile(BytesIO(template_bytes))
    out = BytesIO()
    edits = {}

    x = zin.read("xl/worksheets/sheet1.xml").decode("utf-8")
    x = _set_cell(x, "C5", basic.get("name", ""), numeric=False)
    x = _set_cell(x, "C6", basic.get("manufacturer", ""), numeric=False)
    x = _set_cell(x, "C7", basic.get("revision", ""), numeric=False)
    comps = list(basic.get("components") or [])
    if len(comps) > 5:                            # 양식 성분 행은 5개
        comps[4] = {"name": ", ".join(c.get("name", "") for c in comps[4:]),
                    "cas": "", "content": ""}
        comps = comps[:5]
    for i, c in enumerate(comps):
        x = _set_cell(x, "C%d" % (9 + i), c.get("name", ""), numeric=False)
        x = _set_cell(x, "D%d" % (9 + i), c.get("cas", ""), numeric=False)
        x = _set_cell(x, "E%d" % (9 + i), c.get("content", ""), numeric=False)
    x = _set_cell(x, "C14", basic.get("dept", ""), numeric=False)
    x = _set_cell(x, "C15", basic.get("storage", ""), numeric=False)
    x = _set_cell(x, "C16", basic.get("purpose", ""), numeric=False)
    x = _set_cell(x, "C17", basic.get("hcodes", ""), numeric=False)
    for key, cell, _label, kind, _unit, _sec in RISK_FIELDS:
        v = str(vals.get(key, "") or "").strip()
        if key == "taboo":                        # 빈칸이면 0 (수식 오류 방지)
            x = _set_cell(x, cell, int(_f(v)) if _f(v) is not None else 0)
        elif kind == "num":
            x = _set_cell(x, cell, v if _f(v) is not None else "없음")
        else:
            x = _set_cell(x, cell, v or None, numeric=False)
    edits["xl/worksheets/sheet1.xml"] = x

    for key, fname in (("2", "sheet2.xml"), ("3", "sheet3.xml"),
                       ("4", "sheet4.xml")):
        sh = sheets.get(key, {})
        x = zin.read("xl/worksheets/" + fname).decode("utf-8")
        for i, s in enumerate(sh.get("scores") or []):
            x = _set_cell(x, "F%d" % (8 + i), int(s))
        for i, note in enumerate(sh.get("notes") or []):
            if note:
                x = _set_cell(x, "M%d" % (8 + i), note, numeric=False)
        opts = poss_options(key)
        for i, idx in enumerate(sh.get("poss") or []):
            if idx is not None:
                x = _set_cell(x, "D%d" % (24 + i), opts[i][idx], numeric=False)
        mit = sh.get("mit") or {}
        tier_rows = {"eng": 59, "op": 60, "adm": 61, "ppe": 62}
        for tier, row in tier_rows.items():
            if tier == "ppe" and not SHEETS[key]["has_ppe"]:
                continue
            for j, no in enumerate((mit.get(tier) or [])[:3]):
                if no:
                    x = _set_cell(x, "%s%d" % ("EGI"[j], row), no,
                                  numeric=False)
        edits["xl/worksheets/" + fname] = x

    x = zin.read("xl/worksheets/sheet5.xml").decode("utf-8")
    x = _set_cell(x, "D3", meta.get("ev_type", ""), numeric=False)
    x = _set_cell(x, "H3", meta.get("ev_date", ""), numeric=False)
    x = _set_cell(x, "D4", meta.get("ev_dept", ""), numeric=False)
    x = _set_cell(x, "H4", meta.get("ev_by", ""), numeric=False)
    x = _set_cell(x, "B57", meta.get("opinion", ""), numeric=False)
    edits["xl/worksheets/sheet5.xml"] = x

    wbxml = zin.read("xl/workbook.xml").decode("utf-8")
    if "fullCalcOnLoad" not in wbxml:             # 열 때 전체 재계산
        wbxml = wbxml.replace("<calcPr ", '<calcPr fullCalcOnLoad="1" ', 1)
    edits["xl/workbook.xml"] = wbxml

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = edits.get(item.filename)
            if data is not None:
                zout.writestr(item.filename, data.encode("utf-8"))
            else:
                zout.writestr(item, zin.read(item.filename))
    return out.getvalue()
