"""실행 가능한 단일 점검. DART 키 없이 돈다.

목적은 커버리지가 아니라 이 프로젝트에서 틀리면 결과 전체가 무의미해지는
세 지점만 붙잡는 것이다: 라벨 시점, 정제 기준의 학습구간 한정, 분할 순서.

    python tests/test_smoke.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hup import dataset, features, model  # noqa: E402


def test_ratio_math():
    a = dict.fromkeys(features.ACCOUNTS, None)
    a.update(assets=1000.0, liabilities=800.0, equity=200.0, capital_stock=500.0,
             revenue=500.0, op_income=-50.0, net_income=-60.0, cur_assets=100.0,
             cur_liab=400.0, cfo=-30.0, interest_exp=0.0)
    r = features.ratios(a)
    assert r["부채비율"] == 4.0
    assert r["유동비율"] == 0.25
    assert r["영업손실"] == 1.0
    assert r["자본잠식"] == 1.0 and r["완전자본잠식"] == 0.0
    assert r["자본잠식률"] == 0.6
    assert np.isnan(r["이자보상배율"]), "분모 0 은 0이 아니라 NaN 이어야 한다"


def test_label_timing():
    """감사의견은 사업보고서 '안에' 있다. 그 보고서로 그 의견을 맞히면 동어반복이다."""
    panel = pd.DataFrame({
        "corp_code": ["A", "A"],
        "bsns_year": [2021, 2022],
        "rcept_dt": pd.to_datetime(["2022-03-25", "2023-03-28"]),
    })
    events = pd.DataFrame({
        "corp_code": ["A"],
        "event_date": pd.to_datetime(["2023-03-28"]),   # FY2022 보고서 접수일 = 의견거절 공표일
        "event_type": ["감사의견"],
    })

    d365 = dataset.attach_labels(panel, events, horizon_days=365)
    fy22 = d365.set_index("bsns_year").loc[2022, "y"]
    assert fy22 == 0, "사건일 == 기준시점이면 이미 알려진 정보다. 라벨이 되면 안 된다"

    # 그리고 이게 계획서 그대로 두면 새는 구멍이다:
    # 제출 간격이 368일이라 12개월 창을 3일 차이로 벗어난다.
    assert d365.set_index("bsns_year").loc[2021, "y"] == 0
    d400 = dataset.attach_labels(panel, events, horizon_days=400)
    assert d400.set_index("bsns_year").loc[2021, "y"] == 1, \
        "창을 400일로 넓히면 잡힌다 → 민감도 분석 없이는 사건이 통째로 사라진다"

    # event_type 은 '창 안에 든 사건'만 가리켜야 한다.
    # 아니면 '이 기업에 언젠가 사건이 있었다'가 되어 y=0 행에도 유형이 붙는다.
    for d in (d365, d400):
        assert d.loc[d["y"] == 0, "event_type"].isna().all(), "y=0 인데 event_type 이 붙었다"
    assert d400.set_index("bsns_year").loc[2021, "event_type"] == "감사의견"


def test_clean_fits_on_train_only():
    rng = np.random.default_rng(0)
    tr = pd.DataFrame({"부채비율": rng.normal(2, 0.5, 500)})
    te = pd.DataFrame({"부채비율": [999.0, np.nan]})
    tr.loc[0, "부채비율"] = np.nan   # 학습 구간에 결측이 있어야 더미 열이 생긴다
    st = dataset.fit_clean(tr, cols=["부채비율"])
    out = dataset.apply_clean(te, st)
    assert out["부채비율"].iloc[0] <= tr["부채비율"].quantile(0.99) + 1e-9, "평가값이 학습 상한으로 잘려야 한다"
    assert out["부채비율"].iloc[1] == st["med"]["부채비율"]
    assert out["부채비율_결측"].tolist() == [0, 1]


def test_split_is_chronological():
    df = pd.DataFrame({
        "rcept_dt": pd.to_datetime([f"{y}-03-20" for y in range(2016, 2026)]),
        "y": [0] * 8 + [1, 1],
    })
    s = dataset.split(df)
    rep = dataset.sanity(s)
    # 개수를 박아두지 않는다 — 분할 정의가 바뀌면 테스트가 깨져야 하는 게 아니라
    # **분할이 시점 순인지**가 깨져야 한다 (sanity 가 이미 검사한다)
    from hup import config
    for k, (a_, b_) in config.SPLIT.items():
        assert rep[k]["n"] == b_ - a_ + 1, f"{k} 구간 행 수가 연도 수와 다르다"
    assert sum(rep[k]["n"] for k in rep) == len(df)


def test_metrics_are_not_accuracy():
    y = np.array([0] * 98 + [1, 1])
    always_zero = np.zeros(100)
    m = model.evaluate(y, always_zero, n_boot=50)
    assert m["재현율@정밀도0.3"] == 0.0, "전부 정상으로 찍는 모형은 0점이어야 한다"
    assert abs(m["PR-AUC"] - model.prevalence_baseline(y)) < 0.05



def test_card_reads_off_the_observed_value():
    """묶음은 SHAP 부호, 문장은 관측값. 이 둘을 섞으면 카드가 거꾸로 읽힌다."""
    from hup import explain
    cols = ["부채비율", "유동비율", "자본잠식", "재고자산회전율"]
    row = pd.Series({"부채비율": 8.0, "유동비율": 0.3, "자본잠식": 1.0, "재고자산회전율": 9.0})
    ref = pd.Series({"부채비율": 1.2, "유동비율": 1.5, "재고자산회전율": 6.0})
    # 부채비율만 SHAP 이 음수 = 모델은 위험을 낮췄다고 본다. 그런데 값은 위험 쪽(8.0 > 1.2)
    txt = explain.card(row, np.array([-0.1, 0.4, 0.3, 0.2]), cols, ref=ref, prob=0.42)
    assert "현금화 가능한 자산이 부족합니다" in txt
    assert "자본잠식" in txt and "실측 1.00" not in txt
    assert "위험을 낮춘 요인" in txt and "부채비율이 높습니다" in txt, \
        "모델이 관측값과 반대로 판단한 지점을 카드가 감추면 안 된다"

    # 변화량·증가율·결측 더미는 카드 문장으로 만들지 않는다 (모델에서 빼는 것과 다름)
    cols2 = cols + ["Δ부채비율", "자산증가율", "부채비율_결측"]
    row2 = pd.concat([row, pd.Series({"Δ부채비율": 3.0, "자산증가율": -0.9, "부채비율_결측": 1.0})])
    t2 = explain.card(row2, np.array([-0.1, 0.4, 0.3, 0.2, 0.9, 0.8, 0.7]), cols2, ref=ref)
    assert "전년 대비" not in t2 and "자산이 줄었습니다" not in t2 and "결측" not in t2


def test_no_shadowed_definitions():
    """같은 이름을 두 번 정의하면 파이썬은 **조용히 나중 것을 쓴다.**

    2026-09-05: `cli.compare` 가 두 번 정의돼 구버전이 이겼고, 인자 없이 호출돼
    RuntimeError 가 났다. 에러가 났으니 다행이지, 시그니처가 같았으면
    구버전이 계속 돌면서 아무도 몰랐을 것이다. dict 중복 키도 같은 종류다.
    """
    import ast
    import collections
    root = Path(__file__).resolve().parents[1]
    problems = []
    for f in sorted((root / "src").rglob("*.py")) + sorted((root / "tests").rglob("*.py")):
        tree = ast.parse(f.read_text())
        names = collections.Counter(
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        for k, c in names.items():
            if c > 1:
                problems.append(f"{f.name}: 함수 '{k}' 가 {c}번 정의됨")
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                for k, c in collections.Counter(keys).items():
                    if c > 1:
                        problems.append(f"{f.name}:{node.lineno}: dict 키 '{k}' 가 {c}번")
    assert not problems, "\n  " + "\n  ".join(problems)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\n전부 통과")
