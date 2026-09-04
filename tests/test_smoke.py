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
    assert rep["train"]["n"] == 7 and rep["valid"]["n"] == 1 and rep["test"]["n"] == 2


def test_metrics_are_not_accuracy():
    y = np.array([0] * 98 + [1, 1])
    always_zero = np.zeros(100)
    m = model.evaluate(y, always_zero, n_boot=50)
    assert m["재현율@정밀도0.3"] == 0.0, "전부 정상으로 찍는 모형은 0점이어야 한다"
    assert abs(m["PR-AUC"] - model.prevalence_baseline(y)) < 0.05



def test_card_reads_off_the_observed_value():
    """묶음은 SHAP 부호, 문장은 관측값. 이 둘을 섞으면 카드가 거꾸로 읽힌다."""
    from hup import explain
    cols = ["부채비율", "유동비율", "자본잠식", "매출증가율"]
    row = pd.Series({"부채비율": 8.0, "유동비율": 0.3, "자본잠식": 1.0, "매출증가율": -0.4})
    ref = pd.Series({"부채비율": 1.2, "유동비율": 1.5})
    txt = explain.card(row, np.array([0.4, 0.3, 0.2, -0.1]), cols, ref=ref, prob=0.42)
    assert "부채비율이 높습니다" in txt
    assert "현금화 가능한 자산이 부족합니다" in txt
    assert "자본잠식" in txt and "실측 1.00" not in txt
    # SHAP 은 위험을 낮췄다고 했지만 매출은 줄었다 → 줄었다고 그대로 쓴다
    assert "위험을 낮춘 요인" in txt and "매출이 줄었습니다" in txt

def test_audit_response_keeps_only_current_period():
    """이 API 는 당기·전기·전전기를 같은 rcept_no 로 준다. 셋 다 쓰면 유령 사건이 생긴다."""
    from hup import labels
    # 2026-09-03 삼성전자 실제 응답 서식 (개행·공백 변형 포함)
    rows = [{"bsns_year": "제55기\n(당기)", "adt_opinion": "적정", "rcept_no": "20240312000736"},
            {"bsns_year": "제54기\n(전기)", "adt_opinion": "의견거절", "rcept_no": "20240312000736"},
            {"bsns_year": "제53기  (전전기)", "adt_opinion": "한정", "rcept_no": "20240312000736"}]
    cur = labels.current_period(rows)
    assert cur["adt_opinion"] == "적정", "전기·전전기 의견이 당기로 새어 들어왔다"
    assert labels.current_period([{"bsns_year": "제75기(당기)", "adt_opinion": "부적정"}])["adt_opinion"] == "부적정"
    assert labels.current_period([]) is None


def test_exclusions_do_not_catch_meritz():
    """'리츠'를 부분문자열로 잡으면 메리츠금융지주가 리츠가 된다."""
    panel = pd.DataFrame({"corp_code": ["A", "B", "C", "D"], "bsns_year": [2023] * 4})
    meta = pd.DataFrame({
        "corp_code": ["A", "B", "C", "D"],
        "corp_name": ["메리츠금융지주", "케이탑리츠", "한화에이스기업인수목적2호", "삼성전자"],
        "induty_code": ["64992", "68112", "661", "26410"],
        "acc_mt": ["12", "12", "12", "12"]})
    kept, dropped = dataset.apply_exclusions(panel, meta)
    why = dict(zip(dropped["corp_code"], dropped["_excl"]))
    assert why["A"] == "금융업", "메리츠는 금융업이지 리츠가 아니다"
    assert why["B"] == "스팩/리츠"
    assert why["C"] == "스팩/리츠", "스팩은 업종코드 661 이라 금융업으로 먼저 걸리면 사유가 틀린다"
    assert kept["corp_code"].tolist() == ["D"]


def test_opinion_classification():
    """실측 표기 변형들. '부적정'이 '적정'을 포함한다는 게 함정이다."""
    from hup import labels
    for t in ["의견거절", "거절", "한정", "한정의견", "부적정의견", "한정(감사범위제한)",
              "감사범위제한으로인한한정", "(별도)의견거절(주3)\n(연결)의견거절(주4)"]:
        assert labels.classify_opinion(t) == "비적정", t
    for t in ["적정", "적정의견", "연결:적정 별도:적정", "적정(공정)", "공정",
              "예외사항없음", "지적사항없음", "적정 (별도/연결)"]:
        assert labels.classify_opinion(t) == "적정", t
    for t in ["", None, "   ", "삼정회계법인", "(주1)"]:
        assert labels.classify_opinion(t) == "불명", repr(t)


def test_winsorize_spares_binary_flags():
    """희귀 이진 지표를 분위 클리핑하면 변수 자체가 사라진다."""
    rng = np.random.default_rng(0)
    tr = pd.DataFrame({"부채비율": rng.normal(2, .5, 1000),
                       "완전자본잠식": (rng.random(1000) < 0.005).astype(float)})
    st = dataset.fit_clean(tr, cols=["부채비율", "완전자본잠식"])
    assert "완전자본잠식" in st["binary"] and "부채비율" in st["clip"]
    out = dataset.apply_clean(tr, st)
    assert out["완전자본잠식"].nunique() == 2, "이진 플래그가 상수로 뭉개졌다"


def test_corp_code_stays_a_string(tmp=None):
    """고유번호는 8자리 문자열이다. 정수로 읽히면 앞자리 0 이 날아간다."""
    import tempfile, os
    from hup import pipeline
    d = pd.DataFrame({"corp_code": ["00126380", "01087079"], "bsns_year": [2023, 2023],
                      "rcept_dt": pd.to_datetime(["2024-03-12", "2024-03-20"]), "y": [0, 1]})
    with tempfile.TemporaryDirectory() as t:
        f = os.path.join(t, "d.csv"); d.to_csv(f, index=False)
        back = pipeline.load(f)
    assert back["corp_code"].tolist() == ["00126380", "01087079"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\n전부 통과")
