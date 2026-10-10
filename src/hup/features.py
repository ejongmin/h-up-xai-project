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


def extract(rows, col="thstrm_amount"):
    """DART 전체 재무제표 응답 → 계정 딕셔너리 (기본은 당기 금액, col="frmtrm_amount" 면 전기).

    account_id 를 먼저 보고, 없을 때만 계정명으로 폴백한다. 둘 다 재무제표 구분 안에서만 찾는다.
    """
    by_id, by_nm = {}, {}
    for r in rows:
        sj = r.get("sj_div")
        v = (r.get(col) or "").replace(",", "").strip()
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


def empty_statement(a):
    """자산총계가 없거나 0 이하 — 빈 재무제표 응답. 재무 변수 전체를 결측으로 둔다 (docs/13 §2-5).

    2026-10-10: 0 으로 채워진 응답에서 '영업손실 아님' 같은 이진 변수가 거짓으로 만들어졌다.
    """
    return a.get("assets") is None or a["assets"] <= 0


def fix_units(df, tol=0.01):
    """보고서 사이 단위 전환을 같은 회사의 다른 공시로 확인해 금액을 고친다 (docs/13 §2).

    같은 회계연도 자산총계는 그 해 보고서(_assets)와 다음 해 보고서의 전기(_assets_prev)에 두 번 나온다.
    둘의 비가 10³·10⁶ (±tol) 이면 단위 전환으로 확인한다. 2026-10-10 실측: 한 회사는 2019년부터 7년 연속
    천원 단위였고(전년 대비 변동 검사로는 전환 첫해만 잡혔다), 자산 5경 원짜리 보고서도 있었다.
    비율은 같은 보고서 안에서 단위가 상쇄되므로 건드리지 않는다. 고치는 것은 금액(_assets, _revenue)과 로그자산.
    반환: (고친 df, 수정 내역 DataFrame)
    """
    df = df.sort_values(["corp_code", "bsns_year"]).copy()
    log = []
    for cc, g in df.groupby("corp_code", sort=False):
        idx = list(g.index)
        m = {idx[0]: 0}            # 보고서별 상대 단위 지수 (log10)
        bad = set()
        for i0, i1 in zip(idx, idx[1:]):
            m[i1] = m[i0]
            if g.at[i1, "bsns_year"] != g.at[i0, "bsns_year"] + 1:
                continue           # 연도가 비면 비교할 공시가 없다 — 같은 단위로 둔다
            a0, p1 = g.at[i0, "_assets"], g.at[i1, "_assets_prev"]
            if not (a0 and p1 and a0 > 0 and p1 > 0):
                continue
            k = np.log10(p1 / a0)
            near = round(k)
            if abs(near) in (3, 6) and abs(10 ** (k - near) - 1) <= tol:
                m[i1] = m[i0] + near
            elif abs(k) > 1:       # 10배 넘게 다른데 10³·10⁶ 이 아님 — 확인 불가
                bad |= {i0, i1}
        if len(set(m.values())) > 1:
            lv = pd.Series(m)
            med = g["_assets"].groupby(lv).median()
            ok = med[(med >= 1e9) & (med <= 6e14)].index
            cnt = lv.value_counts()
            pool = [x for x in cnt.index if x in ok] or list(cnt.index)
            base = max(pool, key=lambda x: (cnt[x], -abs(x)))
            for i, x in m.items():
                if x != base:
                    f = 10.0 ** (x - base)
                    log.append({"corp_code": cc, "bsns_year": g.at[i, "bsns_year"], "처리": f"금액 ÷ 10^{x - base}",
                                "자산_수정전": g.at[i, "_assets"], "자산_수정후": g.at[i, "_assets"] / f})
                    for c in ("_assets", "_revenue"):
                        df.at[i, c] = df.at[i, c] / f if pd.notna(df.at[i, c]) else df.at[i, c]
                    a = df.at[i, "_assets"]
                    df.at[i, "로그자산"] = np.log(a) if pd.notna(a) and a > 0 else np.nan
        for i in bad:
            log.append({"corp_code": cc, "bsns_year": g.at[i, "bsns_year"], "처리": "확인 불가 — 로그자산·증가율 결측",
                        "자산_수정전": g.at[i, "_assets"], "자산_수정후": np.nan})
            df.at[i, "로그자산"] = np.nan
            df.at[i, "_unit_unconfirmed"] = 1
    return df, pd.DataFrame(log)


CHANGE_VARS = ["영업이익률", "ROA", "부채비율", "유동비율", "총자산회전율", "영업현금흐름_매출"]


def add_changes(df, keys=("corp_code",), year_col="bsns_year"):
    """전년 대비 변화폭. 수준값만큼 중요하다."""
    df = df.sort_values(list(keys) + [year_col]).copy()
    g = df.groupby(list(keys))
    for c in CHANGE_VARS:
        df[f"Δ{c}"] = df[c] - g[c].shift(1)
    # 분모 0 이면 무한대가 된다 — 결측으로 (docs/13 §2-6)
    df["매출증가율"] = g["_revenue"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) if "_revenue" in df else np.nan
    df["자산증가율"] = g["_assets"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) if "_assets" in df else np.nan
    if "_unit_unconfirmed" in df:     # 단위를 확인할 수 없는 해의 금액은 증가율 계산에 쓰지 않는다
        u = df["_unit_unconfirmed"].fillna(0) == 1
        u_prev = g["_unit_unconfirmed"].shift(1).fillna(0) == 1
        df.loc[u | u_prev, ["매출증가율", "자산증가율"]] = np.nan
    df["2년연속영업손실"] = ((df["영업손실"] == 1) & (g["영업손실"].shift(1) == 1)).astype(float)
    return df


FEATURE_COLS = (
    list(ratios({k: None for k in ACCOUNTS}).keys())
    + [f"Δ{c}" for c in CHANGE_VARS]
    + ["매출증가율", "자산증가율", "2년연속영업손실"]
)
