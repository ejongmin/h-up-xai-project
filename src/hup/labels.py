"""부실 사건 라벨.

주 정의  : 감사의견 비적정(의견거절·부적정·한정) 또는 회생절차 개시 신청
보조 정의: 주 정의 + 재무 사유 관리종목 지정  (강건성 검증용)

가장 조심할 지점 — 감사의견은 그 사업연도 사업보고서 '안에' 들어 있다.
FY2023 재무제표로 FY2023 감사의견을 맞히면 그건 예측이 아니라 동어반복이다.
그래서 사건 시점은 '그 의견이 실린 보고서의 접수일자'로 잡고,
피처는 그보다 앞선 보고서에서만 가져온다. 이 규칙은 dataset.py 가 강제한다.
"""
import csv
import json

import pandas as pd

from . import config, dart


def current_period(rows):
    """감사의견 응답에서 '당기' 행 하나만 고른다.

    이 API 는 한 번 호출에 당기·전기·전전기 3개 행을 **같은 rcept_no 로** 돌려준다.
    전부 쓰면 과거 의견이 나중 보고서 접수일에 다시 사건으로 잡히는 유령 사건이 생긴다.
    구분 문자열은 '제55기\n(당기)', '제76기 (당기)', '제75기(당기)' 처럼 서식이 제각각이라
    공백을 지우고 '당기' 포함 여부로 고른다('전기'·'전전기'에는 '당기'가 없다).
    """
    for r in rows:
        if "당기" in (r.get("bsns_year") or "").replace(" ", "").replace("\n", ""):
            return r
    return rows[0] if rows else None      # 서식이 다르면 첫 행(DART 는 당기를 먼저 준다)


def classify_opinion(text):
    """감사의견 자유 텍스트 → '비적정' / '적정' / '불명'

    '불명'을 따로 두는 게 핵심이다. 빈 값이 5.6%(1,175/20,668)인데 이걸 조용히
    '적정'으로 취급하면 그만큼 사건을 놓치고, 그 사실조차 모르게 된다.
    """
    op = (text or "").replace(" ", "").replace("\n", "")
    if not op:
        return "불명"
    if any(k in op for k in config.ADVERSE_OPINIONS):
        return "비적정"          # '부적정'이 '적정'을 포함하므로 반드시 먼저 본다
    if any(k in op for k in config.CLEAN_OPINIONS):
        return "적정"
    return "불명"


def opinion_coverage(corp_codes, years):
    """감사의견 커버리지. 3주차 산출물 — '불명'이 어디에 몰려 있는지 본다."""
    rows = []
    for cc in corp_codes:
        for y in years:
            r = current_period(dart.audit_opinion(cc, y))
            rows.append({"corp_code": cc, "bsns_year": int(y),
                         "판정": "응답없음" if r is None
                                 else classify_opinion(r.get("adt_opinion"))})
    return pd.DataFrame(rows)


def audit_events(corp_codes, years):
    """감사의견 비적정 사건. 반환: corp_code, event_date, event_type, detail"""
    rows = []
    for cc in corp_codes:
        for y in years:
            r = current_period(dart.audit_opinion(cc, y))
            if not r:
                continue
            op = (r.get("adt_opinion") or "").replace(" ", "")
            if classify_opinion(op) == "비적정":
                rows.append({
                    "corp_code": cc, "bsns_year": int(y),
                    "event_type": "감사의견", "detail": op,
                    "event_date": r.get("rcept_no", "")[:8],   # 접수번호 앞 8자리 = 접수일자
                })
    return pd.DataFrame(rows)


# 감사인이 재무제표 밖에서 남기는 신호. 같은 응답에 이미 들어 있어 추가 호출이 없다.
GOING_CONCERN = ("계속기업", "존속능력", "불확실성")


def audit_matters(corp_codes, years):
    """강조사항·핵심감사사항·특기사항. 13주차 '담기지 않는 정보' 분석의 재료.

    이 항목들은 그 사업연도 보고서에 실리므로 기준시점 T 가 재무제표와 같다.
    즉 패널에 (corp_code, bsns_year) 로 그냥 붙이면 시점 정합이 자동으로 맞는다.
    """
    out = []
    for cc in corp_codes:
        for y in years:
            r = current_period(dart.audit_opinion(cc, y))
            if not r:
                continue
            emph = (r.get("emphs_matter") or "").strip()
            core = (r.get("core_adt_matter") or "").strip()
            spc = (r.get("adt_reprt_spcmnt_matter") or "").strip()
            blob = f"{emph} {spc}"
            out.append({
                "corp_code": cc, "bsns_year": int(y),
                "감사의견": (r.get("adt_opinion") or "").replace(" ", ""),
                "감사인": r.get("adtor", ""),
                "강조사항": emph, "핵심감사사항": core, "특기사항": spc,
                "계속기업불확실성": float(any(k in blob for k in GOING_CONCERN)),
                "강조사항있음": float(emph not in ("", "-", "해당사항 없음", "해당사항없음")),
            })
    return pd.DataFrame(out)


def rehab_events(bgn_de, end_de):
    """회생절차 관련 주요사항보고서. 보고서명으로 거른다.

    개시신청·개시결정이 몇 주 간격으로 따로 온다(예: 필로시스 2023-02-08 신청,
    2023-03-20 결정). 둘 다 남긴다 — labels.build 가 (기업, 날짜, 유형)으로 중복만 지우고,
    라벨은 '창 안에 사건이 하나라도 있는가'이므로 중복 계상 문제가 없다.
    """
    rows = []
    for d in dart.disclosures_all(bgn_de, end_de, pblntf_ty="B"):   # B = 주요사항보고
        nm = d.get("report_nm", "")
        if any(k in nm for k in config.REHAB_KEYWORDS):
            rows.append({"corp_code": d["corp_code"], "bsns_year": int(d["rcept_dt"][:4]),
                         "event_type": "회생절차", "detail": nm, "event_date": d["rcept_dt"]})
    return pd.DataFrame(rows)


def manual_events(path=None):
    """KIND 에서 받아 손으로 정리한 관리종목/상장폐지 표 (보조 정의용).

    data/manual/kind_events.csv 형식: corp_code,event_date,event_type,detail,reason_is_financial
    reason_is_financial 이 Y 인 행만 쓴다. 비재무 사유(공시불이행·지분분산 등)는 부실이 아니다.
    """
    path = path or (config.MANUAL / "kind_events.csv")
    if not path.exists():
        return pd.DataFrame(columns=["corp_code", "bsns_year", "event_type", "detail", "event_date"])
    df = pd.read_csv(path, dtype=str)
    df = df[df["reason_is_financial"].str.upper() == "Y"]
    df["bsns_year"] = df["event_date"].str[:4].astype(int)
    return df[["corp_code", "bsns_year", "event_type", "detail", "event_date"]]


def build(corp_codes, years, bgn_de, end_de, include_secondary=False):
    parts = [audit_events(corp_codes, years), rehab_events(bgn_de, end_de)]
    if include_secondary:
        parts.append(manual_events())
    ev = pd.concat([p for p in parts if len(p)], ignore_index=True)
    ev["event_date"] = pd.to_datetime(ev["event_date"], format="%Y%m%d", errors="coerce")
    ev = ev.dropna(subset=["event_date"])
    # 같은 기업의 같은 날 중복 사건은 하나로
    return ev.sort_values("event_date").drop_duplicates(["corp_code", "event_date", "event_type"])
