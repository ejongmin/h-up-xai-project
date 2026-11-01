"""데이터 검사 관문 — 통과해야 저장·학습된다 (docs/15 §4).

1차 연구의 오류는 전부 에러 없이 조용히 지나갔다(단위 1000배, 정정본 날짜, 자기 연도 라벨).
그래서 두 등급으로 나눈다.
  중단 — 시점 순서·사건 중복처럼 결과를 무효로 만드는 위반. 하나라도 있으면 GateError 로 멈춘다.
  검토 — 단위 의심처럼 틀렸을 수 있는 값. 조용히 고치지 않고 `검토필요=1` 로 표시해 학습·평가에서 빼고
         목록을 남긴다. 사람이 data/manual/검토판정_v2.csv 에 '유지'라고 적은 행만 다시 들어간다.
기준(배율·임계값)은 docs/15 §4 에 결과를 보기 전에 적어 둔 값이다.
"""
import numpy as np
import pandas as pd

from . import config

NO_SOURCE = []          # 원본 XBRL 이 없어 패널에서 빠진 행 (pipeline.panel 이 채운다)
TIME_UNCONFIRMED = []   # 접수번호 날짜가 목록 접수일보다 늦고 원문 확인 목록에 없어 최초 공개 자료인지 확인할 수 없는 행 — 주 분석 제외


class GateError(RuntimeError):
    pass


def hard_failures(df, ev, horizon=None):
    """결과를 무효로 만드는 위반. {검사: 건수}"""
    h = pd.Timedelta(horizon or config.HORIZON_DAYS, "D")
    out = {}
    if "_data_rcept" in df:
        d = pd.to_datetime(df["_data_rcept"].astype(str), format="%Y%m%d", errors="coerce")
        out["재무 공개일 > 기준시점 T"] = int((d > df["rcept_dt"]).sum())
    m = df[df["y"] == 1][["corp_code", "rcept_dt"]].merge(ev[["corp_code", "event_date"]], on="corp_code")
    in_win = (m["event_date"] > m["rcept_dt"]) & (m["event_date"] <= m["rcept_dt"] + h)
    out["라벨 1 인데 창 안 사건 없음"] = int((~in_win.groupby([m["corp_code"], m["rcept_dt"]]).any()).sum())
    out["사건 중복 (기업·날짜·유형)"] = int(ev.duplicated(["corp_code", "event_date", "event_type"]).sum())
    out["기업-연도 중복"] = int(df.duplicated(["corp_code", "bsns_year"]).sum())
    return out


def review_flags(df):
    """검토 대상 사유. 반환: 사유 문자열 Series ('' 이면 통과)."""
    r = pd.Series("", index=df.index)

    def add(mask, why):
        r.loc[mask] = r.loc[mask] + np.where(r.loc[mask] == "", why, "; " + why)

    a = df.get("_assets")
    if a is not None:
        add(a.notna() & (a > 0) & (a < 1e9), "자산 10억 원 미만 (단위 의심)")
    if "_unit_unconfirmed" in df:
        add(df["_unit_unconfirmed"].fillna(0) == 1, "자산 수백 배 변동, 같은 보고서 전기값이 확인 안 함")
    if "_assets_prev" in df:
        # 이번 보고서의 전기값 ÷ 전년 보고서의 당기값이 10ᵏ 근처면 어느 한쪽 단위가 틀렸다.
        # v2.1: 단위 보정 전 원본 값끼리 비교하고, 단위 보정(fix_units)이 이미 고친 행(올해·전년)은 걸지 않는다 — 고친 47행을 잘못 빼고 있었다
        raw = df["_assets_raw"] if "_assets_raw" in df else df["_assets"]
        fixed = (df["_assets"] != raw) & df["_assets"].notna()
        g = df.sort_values(["corp_code", "bsns_year"]).groupby("corp_code")
        prev_own = g["_assets_raw" if "_assets_raw" in df else "_assets"].shift(1).reindex(df.index)
        order = df.sort_values(["corp_code", "bsns_year"]).index
        prev_fixed = fixed.loc[order].groupby(df.loc[order, "corp_code"]).shift(1).fillna(False).astype(bool).reindex(df.index)
        consec = (df["bsns_year"] - g["bsns_year"].shift(1).reindex(df.index)) == 1
        ratio = df["_assets_prev"] / prev_own
        k = np.log10(ratio.where(ratio > 0)).round()
        add(consec & k.abs().isin([3, 6]) & ~fixed & ~prev_fixed, "전기값과 전년 보고서 값이 10³·10⁶ 배 차이 (단위 보정으로 고치지 못함)")
    if "_통화" in df:       # v2.1: 원화가 아닌 통화로 낸 공시 — 금액(규모·증가율)을 원화로 볼 수 없다
        c = df["_통화"].fillna("").astype(str)
        add((c != "") & (c != "KRW"), "통화 단위가 원화가 아님")
    return r


def basis_switch(df):
    """연결↔별도 기준이 전년과 바뀐 행 — 변화량 변수를 결측으로 둔다 (수준이 다른 두 값의 차이라서)."""
    g = df.sort_values(["corp_code", "bsns_year"]).groupby("corp_code")["재무제표기준"]
    prev = g.shift(1).reindex(df.index)
    return prev.notna() & (prev != df["재무제표기준"])


def gate(df, ev, horizon=None):
    """검사 → 보고서 저장 → 중단 위반이 있으면 멈춤. 반환: 검토필요·검토사유 열이 붙은 df."""
    from . import features
    hard = hard_failures(df, ev, horizon)
    df = df.copy()
    sw = basis_switch(df) if "재무제표기준" in df else pd.Series(False, index=df.index)
    chg = [f"Δ{c}" for c in features.CHANGE_VARS] + ["매출증가율", "자산증가율", "2년연속영업손실"]
    df.loc[sw, [c for c in chg if c in df]] = np.nan
    df["검토사유"] = review_flags(df)
    keep = _manual_keep()
    df["검토필요"] = ((df["검토사유"] != "") & ~df.set_index(["corp_code", "bsns_year"]).index.isin(keep)).astype(int)

    out = config.RESULTS / "data_check"
    out.mkdir(parents=True, exist_ok=True)
    cols = ["corp_code", "bsns_year", "rcept_dt", "재무제표기준", "_assets", "_assets_prev", "y", "검토사유"]
    df.loc[df["검토사유"] != "", [c for c in cols if c in df]].to_csv(out / "검토대상.csv", index=False, encoding="utf-8-sig")
    summary = pd.DataFrame(
        [{"등급": "중단", "검사": k, "건수": v} for k, v in hard.items()]
        + [{"등급": "검토", "검사": "검토 대상 행 (학습·평가 제외)", "건수": int(df["검토필요"].sum())},
           {"등급": "검토", "검사": "그중 사건 행", "건수": int(df.loc[df["검토필요"] == 1, "y"].sum())},
           {"등급": "처리", "검사": "연결↔별도 기준 변경 → 변화량 결측", "건수": int(sw.sum())},
           {"등급": "처리", "검사": "원본 XBRL 없음 → 패널 제외 (1차에서 재무가 비어 빠졌던 행 포함)", "건수": len(NO_SOURCE)},
           {"등급": "처리", "검사": "최초 공개 자료 확인 불가(재등록 파일) → 주 분석 제외", "건수": len(TIME_UNCONFIRMED)}])
    pd.DataFrame(TIME_UNCONFIRMED).to_csv(out / "시점확인불가.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "검사요약.csv", index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))
    bad = {k: v for k, v in hard.items() if v}
    if bad:
        raise GateError(f"데이터 검사 중단 위반: {bad} — {out / '검사요약.csv'}")
    return df


def _manual_keep():
    f = config.MANUAL / "검토판정_v2.csv"
    if not f.exists():
        return set()
    m = pd.read_csv(f, dtype={"corp_code": str})
    m = m[m["판정"].astype(str).str.strip() == "유지"]
    return set(zip(m["corp_code"], m["bsns_year"].astype(int)))
