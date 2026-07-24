# -*- coding: utf-8 -*-
"""유해화학물질 규격표지용 내장 화학물질 정보.

물질명(또는 별칭·CAS 번호)을 입력하면 CAS 번호·국제연합번호(UN No.)·
GHS 그림문자를 자동으로 채우기 위한 참고용 요약 데이터.
산업 현장에서 흔히 취급하는 유해화학물질 약 80종을 담았다.

주의: 참고용 요약이므로 실제 표지 제작 전에 해당 제품의 MSDS·
화학물질정보처리시스템(KREACH) 정보와 반드시 대조해 확인해야 한다.
(같은 물질이라도 농도·제형에 따라 분류가 달라질 수 있다.)
"""

# name: 대표 물질명(국문) / alias: 별칭·영문명 / cas: CAS No. /
# un: 국제연합번호(4자리, 없으면 "") / pics: GHS 그림문자
CHEM_DB = [
    # ── 산·염기 ──
    {"name": "황산", "alias": ["sulfuric acid", "sulphuric acid"],
     "cas": "7664-93-9", "un": "1830", "pics": ["GHS05"]},
    {"name": "질산", "alias": ["nitric acid"],
     "cas": "7697-37-2", "un": "2031", "pics": ["GHS03", "GHS05", "GHS06"]},
    {"name": "염산", "alias": ["염화수소산", "hydrochloric acid"],
     "cas": "7647-01-0", "un": "1789", "pics": ["GHS05", "GHS07"]},
    {"name": "플루오린화수소산", "alias": ["불산", "불화수소산", "hydrofluoric acid"],
     "cas": "7664-39-3", "un": "1790", "pics": ["GHS05", "GHS06"]},
    {"name": "인산", "alias": ["phosphoric acid"],
     "cas": "7664-38-2", "un": "1805", "pics": ["GHS05"]},
    {"name": "아세트산", "alias": ["초산", "빙초산", "acetic acid"],
     "cas": "64-19-7", "un": "2789", "pics": ["GHS02", "GHS05"]},
    {"name": "포름산", "alias": ["개미산", "formic acid"],
     "cas": "64-18-6", "un": "1779", "pics": ["GHS02", "GHS05", "GHS06"]},
    {"name": "클로로설폰산", "alias": ["클로로술폰산", "chlorosulfonic acid"],
     "cas": "7790-94-5", "un": "1754", "pics": ["GHS05", "GHS06"]},
    {"name": "수산화나트륨", "alias": ["가성소다", "sodium hydroxide"],
     "cas": "1310-73-2", "un": "1823", "pics": ["GHS05"]},
    {"name": "수산화칼륨", "alias": ["가성가리", "potassium hydroxide"],
     "cas": "1310-58-3", "un": "1813", "pics": ["GHS05", "GHS07"]},
    {"name": "암모니아", "alias": ["ammonia"],
     "cas": "7664-41-7", "un": "1005",
     "pics": ["GHS04", "GHS05", "GHS06", "GHS09"]},
    {"name": "암모니아수", "alias": ["수산화암모늄", "ammonia solution",
                                     "ammonium hydroxide"],
     "cas": "1336-21-6", "un": "2672", "pics": ["GHS05", "GHS09"]},
    # ── 산화제·과산화물 ──
    {"name": "과산화수소", "alias": ["hydrogen peroxide"],
     "cas": "7722-84-1", "un": "2014", "pics": ["GHS03", "GHS05", "GHS07"]},
    {"name": "차아염소산나트륨", "alias": ["하이포아염소산나트륨",
                                           "sodium hypochlorite"],
     "cas": "7681-52-9", "un": "1791", "pics": ["GHS05", "GHS09"]},
    {"name": "질산암모늄", "alias": ["ammonium nitrate"],
     "cas": "6484-52-2", "un": "1942", "pics": ["GHS03", "GHS07"]},
    {"name": "질산칼륨", "alias": ["potassium nitrate"],
     "cas": "7757-79-1", "un": "1486", "pics": ["GHS03"]},
    {"name": "질산나트륨", "alias": ["sodium nitrate"],
     "cas": "7631-99-4", "un": "1498", "pics": ["GHS03", "GHS07"]},
    {"name": "질산은", "alias": ["silver nitrate"],
     "cas": "7761-88-8", "un": "1493", "pics": ["GHS03", "GHS05", "GHS09"]},
    {"name": "과망가니즈산칼륨", "alias": ["과망간산칼륨", "potassium permanganate"],
     "cas": "7722-64-7", "un": "1490",
     "pics": ["GHS03", "GHS07", "GHS08", "GHS09"]},
    {"name": "다이크로뮴산칼륨", "alias": ["중크롬산칼륨", "potassium dichromate"],
     "cas": "7778-50-9", "un": "3288",
     "pics": ["GHS03", "GHS05", "GHS06", "GHS08", "GHS09"]},
    {"name": "삼산화크로뮴", "alias": ["무수크롬산", "크롬산", "chromium trioxide"],
     "cas": "1333-82-0", "un": "1463",
     "pics": ["GHS03", "GHS05", "GHS06", "GHS08", "GHS09"]},
    {"name": "과황산암모늄", "alias": ["퍼설페이트암모늄", "ammonium persulfate",
                                       "ammonium peroxydisulfate"],
     "cas": "7727-54-0", "un": "1444", "pics": ["GHS03", "GHS07", "GHS08"]},
    {"name": "과황산나트륨", "alias": ["sodium persulfate"],
     "cas": "7775-27-1", "un": "1505", "pics": ["GHS03", "GHS07", "GHS08"]},
    {"name": "과황산칼륨", "alias": ["potassium persulfate"],
     "cas": "7727-21-1", "un": "1492", "pics": ["GHS03", "GHS07", "GHS08"]},
    # ── 방향족·탄화수소 용제 ──
    {"name": "톨루엔", "alias": ["toluene"],
     "cas": "108-88-3", "un": "1294", "pics": ["GHS02", "GHS07", "GHS08"]},
    {"name": "벤젠", "alias": ["benzene"],
     "cas": "71-43-2", "un": "1114", "pics": ["GHS02", "GHS07", "GHS08"]},
    {"name": "크실렌", "alias": ["자일렌", "xylene"],
     "cas": "1330-20-7", "un": "1307", "pics": ["GHS02", "GHS07", "GHS08"]},
    {"name": "스티렌", "alias": ["styrene"],
     "cas": "100-42-5", "un": "2055", "pics": ["GHS02", "GHS07", "GHS08"]},
    {"name": "노말헥산", "alias": ["n-헥산", "헥산", "hexane", "n-hexane"],
     "cas": "110-54-3", "un": "1208",
     "pics": ["GHS02", "GHS07", "GHS08", "GHS09"]},
    {"name": "사이클로헥산", "alias": ["시클로헥산", "cyclohexane"],
     "cas": "110-82-7", "un": "1145",
     "pics": ["GHS02", "GHS07", "GHS08", "GHS09"]},
    # ── 알코올·케톤·에스터 용제 ──
    {"name": "메탄올", "alias": ["메틸알코올", "methanol", "methyl alcohol"],
     "cas": "67-56-1", "un": "1230", "pics": ["GHS02", "GHS06", "GHS08"]},
    {"name": "에탄올", "alias": ["에틸알코올", "주정", "ethanol", "ethyl alcohol"],
     "cas": "64-17-5", "un": "1170", "pics": ["GHS02", "GHS07"]},
    {"name": "이소프로필알코올", "alias": ["2-프로판올", "이소프로판올", "ipa",
                                           "isopropyl alcohol", "isopropanol"],
     "cas": "67-63-0", "un": "1219", "pics": ["GHS02", "GHS07"]},
    {"name": "아세톤", "alias": ["acetone"],
     "cas": "67-64-1", "un": "1090", "pics": ["GHS02", "GHS07"]},
    {"name": "메틸에틸케톤", "alias": ["2-부타논", "mek", "methyl ethyl ketone"],
     "cas": "78-93-3", "un": "1193", "pics": ["GHS02", "GHS07"]},
    {"name": "메틸이소부틸케톤", "alias": ["mibk", "methyl isobutyl ketone"],
     "cas": "108-10-1", "un": "1245", "pics": ["GHS02", "GHS07"]},
    {"name": "에틸아세테이트", "alias": ["초산에틸", "아세트산에틸", "ethyl acetate"],
     "cas": "141-78-6", "un": "1173", "pics": ["GHS02", "GHS07"]},
    {"name": "부틸아세테이트", "alias": ["초산부틸", "butyl acetate"],
     "cas": "123-86-4", "un": "1123", "pics": ["GHS02", "GHS07"]},
    {"name": "테트라하이드로퓨란", "alias": ["테트라히드로푸란", "thf",
                                             "tetrahydrofuran"],
     "cas": "109-99-9", "un": "2056", "pics": ["GHS02", "GHS07", "GHS08"]},
    {"name": "1,4-다이옥세인", "alias": ["1,4-디옥산", "디옥산", "1,4-dioxane"],
     "cas": "123-91-1", "un": "1165", "pics": ["GHS02", "GHS07", "GHS08"]},
    # ── 할로겐화 용제 ──
    {"name": "디클로로메탄", "alias": ["염화메틸렌", "메틸렌클로라이드",
                                       "dichloromethane", "methylene chloride"],
     "cas": "75-09-2", "un": "1593", "pics": ["GHS07", "GHS08"]},
    {"name": "클로로포름", "alias": ["트리클로로메탄", "chloroform"],
     "cas": "67-66-3", "un": "1888", "pics": ["GHS06", "GHS08"]},
    {"name": "사염화탄소", "alias": ["carbon tetrachloride"],
     "cas": "56-23-5", "un": "1846", "pics": ["GHS06", "GHS08"]},
    {"name": "트리클로로에틸렌", "alias": ["tce", "trichloroethylene"],
     "cas": "79-01-6", "un": "1710", "pics": ["GHS07", "GHS08"]},
    {"name": "퍼클로로에틸렌", "alias": ["테트라클로로에틸렌", "pce",
                                         "perchloroethylene",
                                         "tetrachloroethylene"],
     "cas": "127-18-4", "un": "1897", "pics": ["GHS07", "GHS08", "GHS09"]},
    # ── 질소·황 함유 용제 등 ──
    {"name": "아세토니트릴", "alias": ["acetonitrile"],
     "cas": "75-05-8", "un": "1648", "pics": ["GHS02", "GHS07"]},
    {"name": "디메틸포름아미드", "alias": ["dmf", "n,n-디메틸포름아미드",
                                           "dimethylformamide"],
     "cas": "68-12-2", "un": "2265", "pics": ["GHS02", "GHS07", "GHS08"]},
    {"name": "피리딘", "alias": ["pyridine"],
     "cas": "110-86-1", "un": "1282", "pics": ["GHS02", "GHS07"]},
    {"name": "이황화탄소", "alias": ["carbon disulfide"],
     "cas": "75-15-0", "un": "1131", "pics": ["GHS02", "GHS07", "GHS08"]},
    # ── 알데하이드·페놀류 ──
    {"name": "포름알데히드", "alias": ["포르말린", "formaldehyde", "formalin"],
     "cas": "50-00-0", "un": "2209", "pics": ["GHS05", "GHS06", "GHS08"]},
    {"name": "페놀", "alias": ["석탄산", "phenol"],
     "cas": "108-95-2", "un": "1671", "pics": ["GHS05", "GHS06", "GHS08"]},
    {"name": "아닐린", "alias": ["aniline"],
     "cas": "62-53-3", "un": "1547", "pics": ["GHS06", "GHS08", "GHS09"]},
    {"name": "니트로벤젠", "alias": ["nitrobenzene"],
     "cas": "98-95-3", "un": "1662", "pics": ["GHS06", "GHS08", "GHS09"]},
    {"name": "벤질클로라이드", "alias": ["염화벤질", "benzyl chloride"],
     "cas": "100-44-7", "un": "1738", "pics": ["GHS06", "GHS08"]},
    # ── 모노머·반응성 물질 ──
    {"name": "아크릴로니트릴", "alias": ["acrylonitrile"],
     "cas": "107-13-1", "un": "1093",
     "pics": ["GHS02", "GHS05", "GHS06", "GHS08", "GHS09"]},
    {"name": "아크릴산", "alias": ["acrylic acid"],
     "cas": "79-10-7", "un": "2218", "pics": ["GHS02", "GHS05", "GHS07", "GHS09"]},
    {"name": "아크릴아미드", "alias": ["acrylamide"],
     "cas": "79-06-1", "un": "3426", "pics": ["GHS06", "GHS07", "GHS08"]},
    {"name": "메틸메타크릴레이트", "alias": ["mma", "methyl methacrylate"],
     "cas": "80-62-6", "un": "1247", "pics": ["GHS02", "GHS07"]},
    {"name": "에피클로로히드린", "alias": ["epichlorohydrin"],
     "cas": "106-89-8", "un": "2023",
     "pics": ["GHS02", "GHS05", "GHS06", "GHS08"]},
    {"name": "에틸렌옥사이드", "alias": ["산화에틸렌", "eo", "ethylene oxide"],
     "cas": "75-21-8", "un": "1040",
     "pics": ["GHS02", "GHS04", "GHS06", "GHS08"]},
    {"name": "프로필렌옥사이드", "alias": ["산화프로필렌", "propylene oxide"],
     "cas": "75-56-9", "un": "1280", "pics": ["GHS02", "GHS07", "GHS08"]},
    {"name": "톨루엔-2,4-디이소시아네이트", "alias": ["tdi",
                                                      "toluene diisocyanate"],
     "cas": "584-84-9", "un": "2078", "pics": ["GHS06", "GHS08"]},
    # ── 아민류 ──
    {"name": "디이소프로필아민", "alias": ["dipa", "diisopropylamine"],
     "cas": "108-18-9", "un": "1158", "pics": ["GHS02", "GHS05", "GHS07"]},
    {"name": "트리에틸아민", "alias": ["triethylamine"],
     "cas": "121-44-8", "un": "1296", "pics": ["GHS02", "GHS05", "GHS06"]},
    {"name": "에틸렌디아민", "alias": ["ethylenediamine"],
     "cas": "107-15-3", "un": "1604",
     "pics": ["GHS02", "GHS05", "GHS07", "GHS08"]},
    {"name": "모노에탄올아민", "alias": ["에탄올아민", "ethanolamine",
                                         "monoethanolamine"],
     "cas": "141-43-5", "un": "2491", "pics": ["GHS05", "GHS07"]},
    {"name": "메틸아민", "alias": ["methylamine"],
     "cas": "74-89-5", "un": "1061",
     "pics": ["GHS02", "GHS04", "GHS05", "GHS07"]},
    {"name": "하이드라진", "alias": ["히드라진", "hydrazine"],
     "cas": "302-01-2", "un": "2029",
     "pics": ["GHS02", "GHS05", "GHS06", "GHS08", "GHS09"]},
    # ── 시안·맹독성 물질 ──
    {"name": "시안화수소", "alias": ["청산", "hydrogen cyanide"],
     "cas": "74-90-8", "un": "1051", "pics": ["GHS02", "GHS06", "GHS09"]},
    {"name": "시안화나트륨", "alias": ["청산소다", "sodium cyanide"],
     "cas": "143-33-9", "un": "1689", "pics": ["GHS06", "GHS09"]},
    {"name": "시안화칼륨", "alias": ["청산가리", "potassium cyanide"],
     "cas": "151-50-8", "un": "1680", "pics": ["GHS06", "GHS09"]},
    # ── 가스 ──
    {"name": "염소", "alias": ["chlorine"],
     "cas": "7782-50-5", "un": "1017",
     "pics": ["GHS03", "GHS04", "GHS06", "GHS09"]},
    {"name": "염화수소", "alias": ["hydrogen chloride"],
     "cas": "7647-01-0", "un": "1050", "pics": ["GHS04", "GHS05", "GHS06"]},
    {"name": "이산화황", "alias": ["아황산가스", "sulfur dioxide"],
     "cas": "7446-09-5", "un": "1079", "pics": ["GHS04", "GHS05", "GHS06"]},
    {"name": "황화수소", "alias": ["hydrogen sulfide"],
     "cas": "7783-06-4", "un": "1053",
     "pics": ["GHS02", "GHS04", "GHS06", "GHS09"]},
    {"name": "일산화탄소", "alias": ["carbon monoxide"],
     "cas": "630-08-0", "un": "1016",
     "pics": ["GHS02", "GHS04", "GHS06", "GHS08"]},
    # ── 금속·무기물 등 ──
    {"name": "브로민", "alias": ["브롬", "bromine"],
     "cas": "7726-95-6", "un": "1744", "pics": ["GHS05", "GHS06", "GHS09"]},
    {"name": "수은", "alias": ["mercury"],
     "cas": "7439-97-6", "un": "2809", "pics": ["GHS06", "GHS08", "GHS09"]},
    {"name": "황린", "alias": ["백린", "yellow phosphorus",
                               "white phosphorus"],
     "cas": "7723-14-0", "un": "1381",
     "pics": ["GHS02", "GHS05", "GHS06", "GHS09"]},
    {"name": "나트륨", "alias": ["금속나트륨", "sodium"],
     "cas": "7440-23-5", "un": "1428", "pics": ["GHS02", "GHS05"]},
    {"name": "칼륨", "alias": ["금속칼륨", "potassium"],
     "cas": "7440-09-7", "un": "2257", "pics": ["GHS02", "GHS05"]},
]


def _norm(s: str) -> str:
    return "".join(str(s or "").split()).lower()


def search_chem(query: str, limit: int = 10):
    """물질명·별칭·CAS 번호로 내장 DB를 검색한다.

    반환: [{"name", "cas", "un", "pictograms"}] — 정확 일치 > 시작 일치 >
    포함 일치 순으로 정렬.
    """
    q = _norm(query)
    if not q:
        return []
    scored = []
    for ent in CHEM_DB:
        keys = [_norm(ent["name"])] + [_norm(a) for a in ent["alias"]] \
             + [_norm(ent["cas"])]
        if any(k == q for k in keys):
            rank = 0
        elif any(k.startswith(q) for k in keys):
            rank = 1
        elif any(q in k for k in keys):
            rank = 2
        else:
            continue
        scored.append((rank, ent))
    if any(r == 0 for r, _ in scored):       # 정확 일치가 있으면 그것만 반환
        scored = [t for t in scored if t[0] == 0]
    scored.sort(key=lambda t: (t[0], t[1]["name"]))
    return [{"name": e["name"], "cas": e["cas"], "un": e["un"],
             "pictograms": list(e["pics"])} for _, e in scored[:limit]]
