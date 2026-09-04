"""합성 데이터로 파이프라인 전 구간을 한 번 통과시킨다.

DART 키가 도착한 날 처음 돌려보는 상황을 만들지 않기 위한 예행연습이다.
데이터가 진짜인지는 여기서 안 본다. 배선이 이어져 있는지만 본다.

    python tests/test_pipeline.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hup import features, market, pipeline  # noqa: E402


def synthetic(n_corp=400, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_corp):
        cc = f"C{i:05d}"
        sick = rng.random() < 0.12          # 언젠가 부실해질 기업
        for k, y in enumerate(range(2015, 2026)):
            drift = 0.25 * k if sick else 0.0
            a = {"assets": 1e11 * rng.lognormal(0, .6), "revenue": 8e10 * rng.lognormal(0, .5)}
            a["liabilities"] = a["assets"] * min(.95, rng.beta(2, 3) + drift * .06)
            a["equity"] = a["assets"] - a["liabilities"]
            a["capital_stock"] = a["equity"] * rng.uniform(.3, 1.4)
            a["op_income"] = a["revenue"] * (rng.normal(.05, .05) - drift * .02)
            a["net_income"] = a["op_income"] * rng.uniform(.4, 1.2)
            a["cur_assets"] = a["assets"] * rng.uniform(.2, .6)
            a["cur_liab"] = a["liabilities"] * rng.uniform(.3, .8)
            a["cfo"] = a["op_income"] * rng.uniform(.2, 1.6)
            a["inventory"] = a["assets"] * rng.uniform(.02, .2)
            a["receivable"] = a["assets"] * rng.uniform(.05, .25)
            a["interest_exp"] = a["liabilities"] * rng.uniform(.01, .05)
            r = features.ratios(a)
            r.update(corp_code=cc, bsns_year=y, _revenue=a["revenue"], _assets=a["assets"],
                     rcept_dt=pd.Timestamp(f"{y+1}-03-{rng.integers(20, 31):02d}"), _sick=sick)
            rows.append(r)
    df = pd.DataFrame(rows)
    # 시장 변수 3종 — 아픈 기업일수록 규모가 작고 수익률이 나쁘고 변동성이 크게
    n = len(df)
    df["시가총액로그"] = 26 + rng.normal(0, 1.2, n) - df["_sick"] * 0.8
    df["초과수익률"] = rng.normal(0, .35, n) - df["_sick"] * .25
    df["특이변동성"] = np.abs(rng.normal(.35, .12, n)) + df["_sick"] * .12
    g = df.groupby(df["rcept_dt"].dt.year)["시가총액로그"]
    df["상대규모"] = df["시가총액로그"] - g.transform("mean")
    df = features.add_changes(df)
    # 라벨: 아픈 기업이 후반부에 사건. 사건 비율 2% 안팎을 맞춘다
    df["y"] = ((df["_sick"]) & (df["bsns_year"] >= 2019) & (rng.random(len(df)) < .18)).astype(int)
    return df.drop(columns=["_sick"])


def test_end_to_end():
    df = synthetic()
    rate = df["y"].mean()
    assert 0.005 < rate < 0.06, f"사건 비율이 현실 범위를 벗어남: {rate:.2%}"

    res = pipeline.train(df)
    rep = res["분할"]
    assert all(rep[k]["사건"] > 0 for k in ("train", "valid", "test")), \
        f"어느 구간에 사건이 0건이면 평가가 불가능하다: {rep}"

    for name in ("로지스틱", "앙상블"):
        m = res["scores"][f"{name}/test"]
        assert m["PR-AUC"] > res["scores"]["기준선(사건비율)"]["PR-AUC"], f"{name}이 기준선 이하"
        assert m["PR-AUC_95CI"][0] < m["PR-AUC"] < m["PR-AUC_95CI"][1] + 1e-9
        assert "정확도" not in m and "Accuracy" not in m

    out, allow = pipeline.cards(res, n=2)
    assert allow, "안정 변수가 하나도 안 남으면 설명 카드를 만들 수 없다"
    assert len(out) == 2
    card = out[0]["card"]
    assert "위험을 높인 요인" in card and "위험을 낮춘 요인" in card
    assert not any(ch.isdigit() and "SHAP" in card for ch in card), "카드에 SHAP 원값이 노출되면 안 된다"
    print("\n--- 카드 예시 ---\n" + card)
    return res


def test_market_vars_ignore_the_future():
    """T 이후 가격을 아무리 바꿔도 T 시점 변수는 변하지 않아야 한다."""
    idx = pd.bdate_range("2021-01-01", "2023-12-31")
    rng = np.random.default_rng(1)
    px = pd.Series(100 * np.cumprod(1 + rng.normal(0, .02, len(idx))), index=idx)
    mkt = px.pct_change().dropna() * 0.4
    T = pd.Timestamp("2023-01-05")

    base = market.variables(px, T, mkt, n_shares=1e7)
    assert not np.isnan(base["초과수익률"]) and not np.isnan(base["특이변동성"])

    tampered = px.copy()
    tampered.loc[T + pd.Timedelta(1, "D"):] *= 50     # 미래를 폭등시킨다
    after = market.variables(tampered, T, mkt, n_shares=1e7)
    for k in ("시가총액로그", "초과수익률", "특이변동성"):
        assert abs(base[k] - after[k]) < 1e-9, f"{k} 가 미래 가격에 반응했다"

    short = market.variables(px.loc[T - pd.Timedelta(60, "D"):], T, mkt, 1e7)
    assert np.isnan(short["특이변동성"]), "관측일이 부족하면 추정하지 않는다"


def test_market_comparison_runs():
    """재무만 / 시장만 / 재무+시장 을 같은 분할로 비교한다."""
    df = synthetic()
    r = pipeline.compare(df)
    assert set(r["결과"]) == {"재무만", "시장만", "재무+시장"}
    for name, sc in r["결과"].items():
        v = sc["앙상블/test"]["PR-AUC"]
        assert v > 0, name
    print("\n--- 3종 비교 (합성) ---")
    print(f"기준선(사건비율) {r['기준선']:.4f}")
    for name, sc in r["결과"].items():
        v = sc["앙상블/test"]
        print(f"  {name:8s} PR-AUC {v['PR-AUC']:.4f} {v['PR-AUC_95CI']}"
              f"  기준선 대비 {v['PR-AUC']/r['기준선']:.1f}배")
    return r


if __name__ == "__main__":
    r = test_end_to_end()
    test_market_vars_ignore_the_future()
    test_market_comparison_runs()
    print("\n분할:", r["분할"])
    for k, v in r["scores"].items():
        if "/test" in k or "기준선" in k:
            print(k, {a: (round(b, 4) if isinstance(b, float) else b)
                      for a, b in v.items() if a in ("PR-AUC", "ROC-AUC", "재현율@정밀도0.3", "사건수")})
    print("\n전 구간 통과")
