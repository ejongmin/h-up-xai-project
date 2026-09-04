"""Shumway(2001) 시장 변수 3개.

계획서 범위는 '재무제표 기반'이다. 이 파일은 그 범위를 넓히려는 게 아니라
**재무제표만으로 어디까지인가를 재는 비교군**을 만들려는 것이다.
Shumway는 Altman·Zmijewski 회계비율의 절반이 유의하지 않고 시장 변수가 강하다고 했다.
그 말이 국내 상장사·우리 라벨에서도 맞는지 숫자로 확인한다.

수집 경로 (2026-09-02 확인)
  pykrx 에서 **일별 시세(get_market_ohlcv)만** 살아 있다.
  시가총액·지수·종목목록 엔드포인트는 응답이 비어 온다. 그래서
    - 시가총액 = 종가 × 발행주식총수(DART `stockTotqySttus`)
    - 시장수익률 = 표본 전체의 동일가중 일별 수익률 (지수 대신 자체 구성)
  로 만든다. 지수를 쓰지 못한 것은 한계로 명시한다.
"""
import json

import numpy as np
import pandas as pd

from . import config, dart

PX = config.CACHE / "px"
WINDOW = 365          # T 이전 1년
MIN_DAYS = 120        # 이보다 짧으면 변동성 추정을 믿지 않는다


def prices(ticker, bgn, end):
    """일별 종가. 종목당 한 번만 받고 디스크에 남긴다."""
    PX.mkdir(parents=True, exist_ok=True)
    f = PX / f"{ticker}_{bgn}_{end}.json"
    if f.exists():
        return pd.read_json(f, typ="series", convert_dates=True)
    from pykrx import stock
    df = stock.get_market_ohlcv(bgn, end, ticker)
    s = df["종가"].astype(float) if len(df) else pd.Series(dtype=float)
    s.to_json(f, date_format="iso")
    return s


def shares(corp_code, year):
    """발행주식총수. DART 정기보고서 주요정보 '주식의 총수 현황'."""
    for r in dart.get("stockTotqySttus.json", corp_code=corp_code,
                      bsns_year=str(year), reprt_code=config.REPRT_ANNUAL):
        v = (r.get("istc_totqy") or "").replace(",", "").strip()
        if v.isdigit() and int(v) > 0:
            return float(v)
    return np.nan


def market_return(px_by_ticker):
    """표본 전체 동일가중 일별 수익률. 지수 엔드포인트가 죽어 있어 직접 만든다."""
    rets = pd.DataFrame({t: s.pct_change() for t, s in px_by_ticker.items() if len(s) > 1})
    return rets.mean(axis=1).dropna()


def variables(px, T, mkt, n_shares):
    """기준시점 T 에서의 시장 변수 3개. T 이후 가격은 한 줄도 쓰지 않는다."""
    T = pd.Timestamp(T)
    # 부등호 비교 대신 라벨 슬라이스. numpy 2.5 에서 DatetimeIndex 비교가
    # DeprecationWarning 을 내고, 장래에 에러가 된다.
    px = px.sort_index()
    w = px.loc[T - pd.Timedelta(WINDOW, "D"):T]
    out = {"시가총액로그": np.nan, "초과수익률": np.nan, "특이변동성": np.nan}
    if len(w) < MIN_DAYS:
        return out

    if n_shares and not np.isnan(n_shares):
        out["시가총액로그"] = float(np.log(w.iloc[-1] * n_shares))

    r = w.pct_change().dropna()
    m = mkt.reindex(r.index).dropna()
    r = r.reindex(m.index)
    if len(r) < MIN_DAYS:
        return out

    out["초과수익률"] = float((1 + r).prod() - (1 + m).prod())

    var_m = float(m.var())
    if var_m > 0:
        beta = float(np.cov(r, m)[0, 1] / var_m)
        resid = r - beta * m
        out["특이변동성"] = float(resid.std() * np.sqrt(252))
    return out


COLS = ["시가총액로그", "초과수익률", "특이변동성", "상대규모"]


def attach(panel, ticker_of, bgn="20140101", end="20261231"):
    """패널에 시장 변수 4개를 붙인다. 상대규모는 같은 시점 표본 평균 대비 값."""
    px = {}
    for cc in panel["corp_code"].unique():
        t = ticker_of.get(cc)
        if t:
            s = prices(t, bgn, end)
            if len(s):
                px[cc] = s
    mkt = market_return(px)

    rows = []
    for _, row in panel.iterrows():
        cc = row["corp_code"]
        v = ({"시가총액로그": np.nan, "초과수익률": np.nan, "특이변동성": np.nan}
             if cc not in px else
             variables(px[cc], row["rcept_dt"], mkt, shares(cc, int(row["bsns_year"]))))
        rows.append(v)
    out = pd.concat([panel.reset_index(drop=True), pd.DataFrame(rows)], axis=1)

    # Shumway 의 relative size: 시장 전체 대비. 지수를 못 쓰므로
    # 같은 접수연도 표본의 평균 log 시가총액을 기준으로 삼는다.
    g = out.groupby(out["rcept_dt"].dt.year)["시가총액로그"]
    out["상대규모"] = out["시가총액로그"] - g.transform("mean")
    return out
