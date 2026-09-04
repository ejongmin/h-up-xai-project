"""재무비율 산출.

원칙: 변수는 30개 안쪽으로 묶는다. 설명 카드를 만들어야 하므로
자동 생성 파생변수는 쓰지 않는다 — 성능이 올라도 설명이 불가능해진다.
"""
import numpy as np
import pandas as pd

# DART fnlttSinglAcntAll 계정 매핑.
#   (재무제표 구분, 후보 account_id, 후보 account_nm)
#
# 구분(sj_div)을 반드시 건다. 같은 계정명이 재무상태표와 현금흐름표에 동시에 나온다
# (예: '재고자산' vs '재고자산의감소(증가)', '매출채권' vs '매출채권의감소(증가)').
# 이름만으로 뽑으면 현금흐름표 값이나 장기채권이 조용히 섞여 들어온다.
# 2026-09-03 표본 100사 실측으로 후보를 정했다.
ACCOUNTS = {
    "assets":        ("BS",  ["ifrs-full_Assets"], ["자산총계"]),
    "liabilities":   ("BS",  ["ifrs-full_Liabilities"], ["부채총계"]),
    "equity":        ("BS",  ["ifrs-full_Equity"], ["자본총계"]),
    "capital_stock": ("BS",  ["ifrs-full_IssuedCapital"], ["자본금"]),
    "cur_assets":    ("BS",  ["ifrs-full_CurrentAssets"], ["유동자산"]),
    "cur_liab":      ("BS",  ["ifrs-full_CurrentLiabilities"], ["유동부채"]),
    "inventory":     ("BS",  ["ifrs-full_Inventories"], ["재고자산", "유동재고자산"]),
    # 매출채권은 두 코드로 갈린다. 유동 항목만 받고 장기매출채권은 제외한다.
    "receivable":    ("BS",  ["dart_ShortTermTradeReceivable",
                              "ifrs-full_TradeAndOtherCurrentReceivables"],
                             ["매출채권", "매출채권및기타채권", "매출채권및기타유동채권"]),
    "revenue":       ("ISC", ["ifrs-full_Revenue"], ["매출액", "수익(매출액)", "영업수익"]),
    "op_income":     ("ISC", ["dart_OperatingIncomeLoss"], ["영업이익", "영업이익(손실)"]),
    "net_income":    ("ISC", ["ifrs-full_ProfitLoss"], ["당기순이익", "당기순이익(손실)"]),
    # 엄밀히는 금융원가 ≠ 이자비용. 이자보상배율 분모로 쓰므로 변수 정의서에 명시한다.
    "interest_exp":  ("ISC", ["ifrs-full_FinanceCosts"], ["이자비용", "금융원가"]),
    "cfo":           ("CF",  ["ifrs-full_CashFlowsFromUsedInOperatingActivities"],
                             ["영업활동현금흐름", "영업활동으로인한현금흐름"]),
}

SJ = {"BS": {"BS"}, "ISC": {"IS", "CIS"}, "CF": {"CF"}}


def extract(rows):
    """DART 전체 재무제표 응답 → 계정 딕셔너리 (당기 금액).

    account_id 를 먼저 보고, 없을 때만 계정명으로 폴백한다. 둘 다 재무제표 구분 안에서만 찾는다.
    """
    by_id, by_nm = {}, {}
    for r in rows:
        sj = r.get("sj_div")
        v = (r.get("thstrm_amount") or "").replace(",", "").strip()
        if v in ("", "-"):
            continue
        try:
            v = float(v)
        except ValueError:
            continue
        by_id.setdefault((sj, r.get("account_id")), v)
        by_nm.setdefault((sj, (r.get("account_nm") or "").replace(" ", "")), v)

    out = {}
    for key, (grp, ids, nms) in ACCOUNTS.items():
        val = None
        for sj in SJ[grp]:
            for aid in ids:
                if val is None:
                    val = by_id.get((sj, aid))
            for nm in nms:
                if val is None:
                    val = by_nm.get((sj, nm))
        out[key] = val
    return out


def _d(a, b):
    """0/None 안전 나눗셈. 분모가 0이면 비율은 정의되지 않는다 — 0이 아니라 NaN."""
    if a is None or b is None or b == 0:
        return np.nan
    return a / b


def ratios(a):
    """한 기업-연도의 재무비율. a 는 extract() 결과."""
    r = {}
    # 수익성
    r["영업이익률"] = _d(a["op_income"], a["revenue"])
    r["순이익률"] = _d(a["net_income"], a["revenue"])
    r["ROA"] = _d(a["net_income"], a["assets"])
    r["총자산영업이익률"] = _d(a["op_income"], a["assets"])
    # 안정성
    r["부채비율"] = _d(a["liabilities"], a["equity"])
    r["자기자본비율"] = _d(a["equity"], a["assets"])
    r["유동비율"] = _d(a["cur_assets"], a["cur_liab"])
    r["이자보상배율"] = _d(a["op_income"], a["interest_exp"])
    # 활동성
    r["총자산회전율"] = _d(a["revenue"], a["assets"])
    r["매출채권회전율"] = _d(a["revenue"], a["receivable"])
    r["재고자산회전율"] = _d(a["revenue"], a["inventory"])
    # 현금흐름
    r["영업현금흐름_매출"] = _d(a["cfo"], a["revenue"])
    r["영업현금흐름_부채"] = _d(a["cfo"], a["liabilities"])
    r["이익의현금전환"] = _d(a["cfo"], a["net_income"])
    # 특수 항목 — 부실 신호로 가장 직접적인 것들
    eq, cap = a["equity"], a["capital_stock"]
    r["자본잠식"] = np.nan if (eq is None or cap in (None, 0)) else float(eq < cap)
    r["완전자본잠식"] = np.nan if eq is None else float(eq < 0)
    r["자본잠식률"] = _d(None if (eq is None or cap is None) else (cap - eq), cap)
    r["영업손실"] = np.nan if a["op_income"] is None else float(a["op_income"] < 0)
    # 규모 통제
    r["로그자산"] = np.nan if not a["assets"] or a["assets"] <= 0 else float(np.log(a["assets"]))
    return r


CHANGE_VARS = ["영업이익률", "ROA", "부채비율", "유동비율", "총자산회전율", "영업현금흐름_매출"]


def add_changes(df, keys=("corp_code",), year_col="bsns_year"):
    """전년 대비 변화폭. 수준값만큼 중요하다."""
    df = df.sort_values(list(keys) + [year_col]).copy()
    g = df.groupby(list(keys))
    for c in CHANGE_VARS:
        df[f"Δ{c}"] = df[c] - g[c].shift(1)
    df["매출증가율"] = g["_revenue"].pct_change(fill_method=None) if "_revenue" in df else np.nan
    df["자산증가율"] = g["_assets"].pct_change(fill_method=None) if "_assets" in df else np.nan
    df["2년연속영업손실"] = ((df["영업손실"] == 1) & (g["영업손실"].shift(1) == 1)).astype(float)
    return df


FEATURE_COLS = (
    list(ratios({k: None for k in ACCOUNTS}).keys())
    + [f"Δ{c}" for c in CHANGE_VARS]
    + ["매출증가율", "자산증가율", "2년연속영업손실"]
)
