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
    full = {"train": "train_full", "valid": "valid", "test": "test"}
    for k, (a_, b_) in config.SPLIT.items():
        assert rep[full[k]]["n"] == b_ - a_ + 1, f"{k} 구간 행 수가 연도 수와 다르다"
    assert sum(rep[full[k]]["n"] for k in config.SPLIT) == len(df)
    # 엠바고: 검증 단계 학습 표본의 라벨 창은 검증 첫날 전에 끝나야 한다 (docs/13 §3)
    h = pd.Timedelta(config.HORIZON_DAYS, "D")
    assert (s["train"]["rcept_dt"] + h < pd.Timestamp(config.SPLIT["valid"][0], 1, 1)).all()
    assert rep["train"]["n"] < rep["train_full"]["n"], "마지막 학습 연도는 라벨 창이 검증으로 넘어가 빠져야 한다"


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
    sv2 = np.array([-0.1, 0.4, 0.3, 0.2, 0.9, 0.8, 0.7])
    t2 = explain.card(row2, sv2, cols2, ref=ref, hold=False)
    assert "전년 대비" not in t2 and "자산이 줄었습니다" not in t2 and "결측" not in t2
    # 그런데 가장 큰 근거가 카드에 못 오르는 변수(Δ부채비율)면 그 카드는 보류한다 (2026-10-11)
    assert "설명 불안정" in explain.card(row2, sv2, cols2, ref=ref)


def test_card_does_not_overstate_absolute_facts():
    """중앙값보다만 나쁜 값에 사실 단정 문장을 쓰면 안 된다 (2026-10-10 정민재 검토).

    순이익률 +1% 에 "순손실 상태입니다", 자본잠식률 −500%(잠식 없음)에
    "자본잠식이 진행되어 있습니다"가 나가고 있었다.
    """
    from hup import explain
    cols = ["순이익률", "자본잠식률", "유동비율"]
    ref = pd.Series({"순이익률": 0.023, "자본잠식률": -8.297, "유동비율": 1.62})
    sv = np.array([0.3, 0.2, 0.1])
    mild = explain.card(pd.Series({"순이익률": 0.01, "자본잠식률": -5.0, "유동비율": 1.2}), sv, cols, ref=ref)
    assert "순손실" not in mild and "자본잠식이 진행" not in mild and "부족합니다" not in mild
    assert "표본 중앙값보다" in mild, "중앙값보다 나쁜 건 사실이므로 상대 문장으로는 남긴다"
    bad = explain.card(pd.Series({"순이익률": -0.2, "자본잠식률": 0.6, "유동비율": 0.5}), sv, cols, ref=ref)
    assert "순손실 상태입니다" in bad and "자본잠식이 진행" in bad and "부족합니다" in bad


def test_unit_switch_confirmed_by_next_report():
    """단위 전환은 같은 회사의 다음 해 공시(전기 금액)로 확인될 때만 고친다 (docs/13 §2).

    2026-10-10: 2019년부터 천원 단위로 바뀐 회사(7년 연속)와 한 해만 100만 배인 보고서가 있었다.
    """
    from hup import features
    df = pd.DataFrame({
        "corp_code": ["A"] * 4 + ["B"] * 3 + ["C"] * 3 + ["D"] * 4,
        "bsns_year": [2018, 2019, 2020, 2021, 2020, 2021, 2022, 2021, 2022, 2023, 2020, 2021, 2022, 2023],
        # A: 2019 부터 천원 단위 (전기 금액도 같은 단위로 공시됨)
        # B: 2021 보고서만 100만 배
        # C: 자기 시계열이 1000배 뛰었는데 어느 공시도 그 배율을 확인하지 않음 (합병일 수도) — 확인 불가
        # D: 2022 보고서 당기 값만 1000배, 그 보고서의 전기 값과 다음 해 전기 값은 정상
        "_assets":      [1.4e11, 1.3e8, 1.5e8, 1.6e8, 5.0e10, 5.2e16, 5.4e10, 7.0e9, 9.0e12, 9.1e12, 7.0e9, 7.2e9, 9.2e12, 8.0e9],
        "_assets_prev": [1.3e11, 1.4e8, 1.3e8, 1.5e8, 4.9e10, 5.0e16, 5.2e10, 6.0e9, 7.0e9, 9.0e12, 6.9e9, 7.0e9, 7.2e9, 7.3e9],
        "_revenue":     [2e11, 2e8, 2e8, 2e8, 3e10, 3e16, 3e10, 1e9, 1e12, 1e12, 1e9, 1e9, 1e12, 1e9],
    })
    df["로그자산"] = np.log(df["_assets"])
    out, log = features.fix_units(df)
    a = out[out.corp_code == "A"].set_index("bsns_year")["_assets"]
    assert a.between(1e11, 2e11).all(), "기준은 연도 수가 아니라 상장사로 가능한 규모의 구간이어야 한다"
    b = out[out.corp_code == "B"].set_index("bsns_year")["_assets"]
    assert abs(b[2021] - 5.2e10) < 1, "확인된 100만 배는 정확히 10⁶ 로 고친다"
    c = out[out.corp_code == "C"].set_index("bsns_year")
    assert pd.isna(c.loc[2022, "로그자산"]), "확인할 수 없는 점프는 그 해를 결측"
    assert c.loc[2021, "로그자산"] > 0 and c.loc[2023, "로그자산"] > 0, "점프와 무관한 해는 그대로"
    # D: 당기 값만 틀린 보고서 — 다음 해 공시 없이는 확인할 수 없다(T 시점 정보만, 2026-10-13).
    # 그 해만 결측으로 두고, 정상인 다음 해를 이상값과 비교해 1000배로 키우면 안 된다.
    d = out[out.corp_code == "D"].set_index("bsns_year")
    assert pd.isna(d.loc[2022, "로그자산"]) and d.loc[[2020, 2021, 2023], "_assets"].lt(1e10).all()
    grown = features.add_changes(out.assign(**{k: 0.0 for k in features.CHANGE_VARS}, 영업손실=0.0))
    assert grown[(grown.corp_code == "C") & (grown.bsns_year.isin([2022, 2023]))]["자산증가율"].isna().all()
    assert np.isfinite(grown["자산증가율"].dropna()).all()
    assert features.empty_statement({"assets": 0.0}) and features.empty_statement({"assets": None})


def test_card_holds_untrustworthy_explanations():
    """믿을 수 없는 설명은 내지 않고 이유를 적는다 (docs/13 §6, 2026-10-11)."""
    from hup import explain
    cols = ["ROA", "유동비율", "자본잠식률", "ROA_결측"]
    ref = pd.Series({"ROA": 0.02, "유동비율": 1.6, "자본잠식률": -8.0})
    ok = pd.Series({"ROA": -0.2, "유동비율": 0.5, "자본잠식률": 0.6, "ROA_결측": 0, "_assets": 5e10})
    sv = np.array([0.5, 0.3, 0.2, 0.0])
    assert "보류" not in explain.card(ok, sv, cols, ref=ref, prob=0.4)
    # 단위 의심
    bad = ok.copy(); bad["_assets"] = 3e8
    assert "단위 의심" in explain.card(bad, sv, cols, ref=ref)
    # 핵심값 결측 — 위험 요인으로 오를 변수의 원본 값이 없다
    m = ok.copy(); m["ROA"] = np.nan
    t = explain.card(m, sv, cols, ref=ref)
    assert "핵심값 결측" in t and "ROA" in t
    # 설명 불안정 — 가장 큰 근거가 결측 더미
    assert "설명 불안정" in explain.card(ok, np.array([0.1, 0.1, 0.1, 0.9]), cols, ref=ref)
    # 방향 충돌 — 가장 큰 위험 요인의 관측값이 안전 쪽
    c = ok.copy(); c["ROA"] = 0.10
    assert "방향 충돌" in explain.card(c, sv, cols, ref=ref)
    # 낮춘 요인의 방향 충돌은 보류 사유가 아니다 (원칙 ①)
    d = ok.copy(); d["자본잠식률"] = 0.6
    assert "보류" not in explain.card(d, np.array([0.5, 0.3, -0.2, 0.0]), cols, ref=ref)


def test_own_year_audit_opinion_is_not_a_label():
    """FY t 보고서에 이미 적힌 비적정 의견은 그 행의 라벨이 아니라 '과거 사건'이다 (2026-10-13).

    감사의견 응답의 rcept_no 는 최신 정정본이라 그 날짜를 쓰면 T 이후 사건이 되어 동어반복이 됐다(131행).
    """
    from hup import dataset, labels
    panel = pd.DataFrame({"corp_code": ["A", "A"], "bsns_year": [2021, 2022],
                          "rcept_dt": pd.to_datetime(["2022-03-21", "2023-03-20"])})
    first = {("A", 2021): "20220321", ("A", 2022): "20230320"}
    # FY2021 비적정, 정정본은 2022-06 에 나왔다 — 사건일은 최초 접수일(2022-03-21)이어야 한다
    ev = pd.DataFrame({"corp_code": ["A"], "bsns_year": [2021], "event_type": ["감사의견"],
                       "detail": ["의견거절"], "event_date": [first[("A", 2021)]]})
    ev["event_date"] = pd.to_datetime(ev["event_date"])
    out = dataset.mark_prior_events(dataset.attach_labels(panel, ev), ev).set_index("bsns_year")
    assert out.loc[2021, "y"] == 0, "자기 보고서에 적힌 의견으로 자기 행을 맞히면 동어반복"
    assert out.loc[2022, "과거사건"] == 1 and out.loc[2021, "과거사건"] == 1
    # 회생: 같은 절차의 후속 공시(정정·결정)는 사건이 아니다
    r = pd.DataFrame({"corp_code": ["B"] * 3, "event_type": ["회생절차"] * 3, "detail": ["신청", "[첨부정정]신청", "개시결정"],
                      "event_date": pd.to_datetime(["2022-01-10", "2022-01-20", "2022-03-01"])})
    assert len(labels.dedupe_rehab(r)) == 1


def test_recall_at_precision_respects_ties():
    """동점 묶음 한가운데서 끊는 임계값은 실제로 쓸 수 없다 (2026-10-13)."""
    from hup import model
    y = np.array([1, 0, 1, 0, 0, 0])
    p = np.array([0.9, 0.5, 0.5, 0.5, 0.5, 0.1])     # 0.5 동점 4개 중 1개만 양성
    # 동점을 무시하면 '0.9 + 0.5 하나'로 정밀도 0.67·재현율 1.0 을 셀 수 있지만, 0.5 묶음은 통째로만 고를 수 있다
    assert model.recall_at_precision(y, p, 0.5) == 0.5


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


def test_docs_match_current_split():
    """문서에 옛 분할이 남아 있으면 실패한다.

    2026-09-22: 분할을 바꾸고 재분석했는데 문서를 갱신하지 않아
    팀원이 옛 숫자로 작업했다. 같은 계수가 문서마다 셋이었다.
    사람이 기억하는 대신 테스트가 잡는다.

    분할을 말하는 문장만 본다 — '2020~2021년 코로나' 같은 서술은 대상이 아니다.
    """
    import re
    from hup import config
    root = Path(__file__).resolve().parents[1]
    ok = {f"{a}~{b}" for a, b in config.SPLIT.values()}
    stale = []
    for f in list((root / "docs").glob("*.md")) + list((root / "weeks").glob("*.md")):
        if "정민재" in f.name:          # 팀원 원문은 그대로 보존한다
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if not re.search(r"(학습|검증|평가)\s*(구간)?\s*[:|]?\s*20\d\d~20\d\d", line):
                continue
            if any(k in line for k in ("단독", "넓혔", "변경", "이전", "옛", "→")):
                continue
            for m in re.findall(r"20\d\d~20\d\d", line):
                if m not in ok:
                    stale.append(f"{f.name}:{i}  {m}  {line.strip()[:70]}")
    assert not stale, "옛 분할 표기가 남아 있다:\n  " + "\n  ".join(stale[:8])


def test_card_handles_negative_equity():
    """완전자본잠식 기업에 '부채비율이 낮아 안전하다'고 쓰면 안 된다."""
    from hup import explain
    cols = ["부채비율", "자기자본비율", "ROA", "재고자산회전율"]
    row = pd.Series({"부채비율": -2.52, "자기자본비율": -0.656,
                     "ROA": -0.936, "재고자산회전율": 9.0})
    ref = pd.Series({"부채비율": 1.2, "자기자본비율": 0.59,
                     "ROA": 0.02, "재고자산회전율": 6.0})
    txt = explain.card(row, np.array([-0.4, -0.3, 0.9, 0.2]), cols, ref=ref, prob=0.58)
    assert "완전 자본잠식" in txt, "자본이 음수라는 사실을 카드가 말해야 한다"
    assert "부채비율이 낮은 편입니다" not in txt
    assert "자기자본이 두텁습니다" not in txt
    assert "부채 의존도가 낮습니다" not in txt
    assert "벌어들이는 이익이 적습니다" in txt, "해석 가능한 변수는 그대로 남아야 한다"
    # 자본잠식률은 분모가 자본금이라 자본이 음수여도 해석된다 — 빼면 안 된다 (2026-10-11)
    row2 = pd.concat([row, pd.Series({"자본잠식률": 2.3})])
    t2 = explain.card(row2, np.array([-0.4, -0.3, 0.5, 0.2, 0.9]), cols + ["자본잠식률"],
                      ref=pd.concat([ref, pd.Series({"자본잠식률": -8.0})]), prob=0.58)
    assert "자본잠식이 진행되어 있습니다" in t2 and "보류" not in t2


def test_counterfactual_rules():
    """반사실은 카드와 같은 모형·같은 제외 규칙을 따르고, 미미한 변화는 싣지 않는다."""
    from hup import explain

    class Stub:
        """부채비율이 낮아지면 확률이 크게, 유동비율은 아주 조금 떨어지는 가짜 모형."""
        def predict_proba(self, X):
            r = X.iloc[0]
            p = 0.9 - 0.4 * (r["부채비율"] < 3) - 0.01 * (r["유동비율"] > 1)
            return np.array([[1 - p, p]])

    cols = ["부채비율", "유동비율"]
    row = pd.Series({"부채비율": 8.0, "유동비율": 0.3})
    ref = pd.Series({"부채비율": 1.2, "유동비율": 1.5})
    base, items = explain.counterfactual(Stub(), row, cols, cols, ref)
    got = [n for n, *_ in items]
    # 자본잠식은 '표본 중앙값'이 아니라 '해소(0)'가 목표여야 한다
    assert explain.cf_target("자본잠식률", ref)[0] == 0.0
    assert "해소" in explain.cf_target("자본잠식률", ref)[1]
    assert "부채비율" in got, "큰 하락은 실려야 한다"
    assert "유동비율" not in got, "1%p 하락은 보여줄 값이 없다"

    _, items2 = explain.counterfactual(Stub(), row, cols, cols, ref,
                                       skip=explain.EQUITY_BASED)
    assert all(n not in explain.EQUITY_BASED for n, *_ in items2)

    # 2026-10-10 정민재 검토: "ROA이(가)" 같은 표기, 바꿀 수 없는 규모를 반사실로 제시하는 것
    ref2 = pd.Series({"ROA": 0.02, "자기자본비율": 0.59, "로그자산": 25.0})
    assert "ROA가 " in explain.cf_target("ROA", ref2)[1]
    assert "자기자본비율이 " in explain.cf_target("자기자본비율", ref2)[1]

    class Size:
        def predict_proba(self, X):
            p = 0.9 - 0.5 * (X.iloc[0]["로그자산"] > 24)
            return np.array([[1 - p, p]])
    _, items3 = explain.counterfactual(Size(), pd.Series({"로그자산": 20.0}), ["로그자산"], ["로그자산"], ref2)
    assert not items3, "자산 규모는 반사실로 제시하지 않는다"


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


def test_no_named_company_with_risk_score_committed():
    """커밋 대상 파일에 '기업 실명 + 모델 위험도 수치'가 함께 있으면 실패한다.

    지원서 공개 원칙: "실명 기업의 개별 위험도 수치는 공개하지 않고
    분석 방법론과 익명화된 사례만 제시한다."

    2026-09-22: results/w12/오분류_사례.csv 가 기업명과 부실확률을 함께 담은 채
    공개 저장소에 올라가 있었다. 원칙을 계획 단계부터 적어두고도 어겼다.
    """
    import csv
    import subprocess
    root = Path(__file__).resolve().parents[1]
    try:
        tracked = subprocess.run(["git", "ls-files", "*.csv"], cwd=root,
                                 capture_output=True, text=True, timeout=10).stdout.split()
    except Exception:
        return                                   # git 이 없으면 검사 생략
    NAME = ("기업", "corp_name", "종목명", "회사명")
    SCORE = ("확률", "prob", "위험도", "score", "부실확률", "예측")
    bad = []
    for rel in tracked:
        f = root / rel
        if not f.exists():
            continue
        try:
            head = next(csv.reader(f.open(encoding="utf-8-sig")))
        except Exception:
            continue
        cols = [c.strip() for c in head]
        has_name = any(any(k in c for k in NAME) for c in cols)
        has_score = any(any(k in c for k in SCORE) for c in cols)
        if has_name and has_score:
            bad.append(f"{rel}  {cols}")
    assert not bad, "실명+위험도 수치가 함께 커밋돼 있다:\n  " + "\n  ".join(bad)


def test_docs_numbers_match_results():
    """문서에 적힌 핵심 수치가 결과 파일과 어긋나면 실패한다.

    2026-09-28: 분석을 다시 돌린 뒤 문서의 손으로 옮긴 숫자를 갱신하지 않아
    삭제 검사 k=1 이 0.212(구) vs 0.254(현), README PR-AUC 가 0.249(구) vs 0.238(현)
    로 어긋났다. 사람이 기억하는 대신 검사가 잡는다.
    """
    import csv
    import json
    root = Path(__file__).resolve().parents[1]
    checks = []

    f = root / "results" / "w11" / "삭제검사.csv"
    if f.exists():
        row = next(csv.DictReader(f.open(encoding="utf-8")))
        checks.append(("삭제검사 k=1", round(float(row["SHAP상위"]), 3),
                       ["docs/20_최종보고서.md", "docs/10_실측결과.md"]))

    f = root / "results" / "final" / "최종성능.json"
    if f.exists():
        j = json.loads(f.read_text())
        v = j["결과"]["앙상블(비보정)"]["PR-AUC"]
        checks.append(("평가 PR-AUC", round(float(v), 3),
                       ["docs/20_최종보고서.md", "docs/10_실측결과.md"]))

    # 현재 결론(v2.1) — README 와 최종보고서 요약이 v2.1 평가 결과와 맞아야 한다 (2026-11-01)
    f = root / "results" / "v2_1" / "final" / "평가결과.json"
    if f.exists():
        r = json.loads(f.read_text())["결과"]
        checks.append(("v2.1 첫 부실 PR-AUC", round(float(r["관측 기간 내 첫 부실 (주 분석)"]["PR-AUC"]), 3),
                       ["README.md", "docs/20_최종보고서.md", "docs/15_2차연구_계획_사전고정.md"]))
        checks.append(("v2.1 전체 PR-AUC", round(float(r["전체 (보조)"]["PR-AUC"]), 3),
                       ["README.md", "docs/20_최종보고서.md", "docs/15_2차연구_계획_사전고정.md"]))

    # 2026-10-10: §3-4·§3-7 이 검증 구간 확대 전 값(유의 11개, ROA 0.311)으로 남아 있었다.
    # 문서 문장에 그대로 들어가는 문구로 대조한다 (파일, 찾을 문구).
    literal = []
    f = root / "results" / "w07" / "계수_군집보정.csv"
    if f.exists():
        rows = list(csv.DictReader(f.open(encoding="utf-8-sig")))
        n = sum(r["유의_보정후"] == "True" for r in rows)
        literal += [("docs/10_실측결과.md", f"보정 후 {n}개"), ("docs/20_최종보고서.md", f"{n}개로 줄었다")]
    f = root / "results" / "w09" / "전역기여도.csv"
    if f.exists():
        name, v = next(csv.reader(f.open(encoding="utf-8-sig").readlines()[1:]))
        literal.append(("docs/10_실측결과.md", f"| {name} | {float(v):.3f}"))

    bad = [f"{rel}: '{tok}' 가 본문에 없다" for rel, tok in literal
           if (root / rel).exists() and tok not in (root / rel).read_text()]
    for name, val, files in checks:
        token = f"{val:.3f}".rstrip("0")
        for rel in files:
            t = (root / rel)
            if not t.exists():
                continue
            if token not in t.read_text():
                bad.append(f"{rel}: {name} = {val} 가 본문에 없다")
    assert not bad, "문서 수치가 결과 파일과 어긋난다:\n  " + "\n  ".join(bad)


def test_xbrl_reads_first_filing_values():
    """원본 XBRL → 당기·전기, 연결 우선, 분기·세부 차원 값 제외 (docs/15 §3)."""
    import io
    import zipfile
    from hup import xbrl

    def ctx(cid, period, member=None, extra=None):
        dims = ""
        if member:
            dims += f'<xbrldi:explicitMember dimension="ifrs:ConsolidatedAndSeparateFinancialStatementsAxis">ifrs:{member}</xbrldi:explicitMember>'
        if extra:
            dims += f'<xbrldi:explicitMember dimension="ifrs:ComponentsOfEquityAxis">{extra}</xbrldi:explicitMember>'
        sc = f"<scenario>{dims}</scenario>" if dims else ""
        return f'<context id="{cid}"><entity><identifier scheme="x">1</identifier></entity><period>{period}</period>{sc}</context>'

    I = lambda d: f"<instant>{d}</instant>"
    D = lambda a, b: f"<startDate>{a}</startDate><endDate>{b}</endDate>"
    doc = ('<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
           'xmlns:ifrs-full="http://xbrl.ifrs.org/taxonomy/2020-03-16/ifrs-full" xmlns:dart="http://dart.fss.or.kr/taxonomy/2020-06-30/ifrs/dart">'
           + ctx("cI", I("2020-12-31"), "ConsolidatedMember") + ctx("pI", I("2019-12-31"), "ConsolidatedMember")
           + ctx("sI", I("2020-12-31"), "SeparateMember") + ctx("cD", D("2020-01-01", "2020-12-31"), "ConsolidatedMember")
           + ctx("qD", D("2020-10-01", "2020-12-31"), "ConsolidatedMember")
           + ctx("eqI", I("2020-12-31"), "ConsolidatedMember", "dart:CapitalSurplusMember")
           + '<ifrs-full:Assets contextRef="cI" unitRef="KRW" decimals="0">5000</ifrs-full:Assets>'
           + '<ifrs-full:Assets contextRef="pI" unitRef="KRW" decimals="0">4000</ifrs-full:Assets>'
           + '<ifrs-full:Assets contextRef="sI" unitRef="KRW" decimals="0">3000</ifrs-full:Assets>'
           + '<ifrs-full:Equity contextRef="eqI" unitRef="KRW" decimals="0">999</ifrs-full:Equity>'
           + '<ifrs-full:Revenue contextRef="cD" unitRef="KRW" decimals="0">700</ifrs-full:Revenue>'
           + '<dart:OperatingIncomeLoss contextRef="qD" unitRef="KRW" decimals="0">-5</dart:OperatingIncomeLoss>'
           + '<entity1:CapitalX xmlns:entity1="http://dart.fss.or.kr/taxonomy/2020-06-30/entity00000001" contextRef="cI" unitRef="KRW" decimals="0">800</entity1:CapitalX>'
           + '<dart:AdjustmentsForFinanceCosts contextRef="cD" unitRef="KRW" decimals="0">99</dart:AdjustmentsForFinanceCosts>'
           + '<unit id="KRW"><measure>iso4217:KRW</measure></unit>'
           + '</xbrl>')
    lab = ('<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"><link:labelLink>'
           '<link:loc xlink:href="e.xsd#entity00000001_CapitalX" xlink:label="L1"/>'
           '<link:label xlink:label="T1" xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="ko">자본금</link:label>'
           '<link:labelArc xlink:from="L1" xlink:to="T1"/>'
           '<link:loc xlink:href="d.xsd#dart_AdjustmentsForFinanceCosts" xlink:label="L2"/>'
           '<link:label xlink:label="T2" xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="ko">금융원가</link:label>'
           '<link:labelArc xlink:from="L2" xlink:to="T2"/></link:labelLink></link:linkbase>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x_2020.xbrl", doc)
        z.writestr("entity00000001_2020-12-31_lab-ko.xml", lab)      # 2024+ 파일 이름 형식 (v2.1)
    by, meta = xbrl.parse(buf.getvalue(), 2020)
    assert meta["통화"] == ["KRW"]
    rows, fs = xbrl.pick(by)
    assert fs == "CFS"
    a, p = features.extract(rows), features.extract(rows, "frmtrm_amount")
    assert a["assets"] == 5000 and p["assets"] == 4000, "연결 당기·전기"
    assert a["revenue"] == 700, "1년 기간 값"
    assert a["op_income"] is None, "분기 기간 값이 연간 값으로 들어오면 안 된다"
    assert a["equity"] is None, "자본 구성요소(세부 차원) 값이 자본총계로 들어오면 안 된다"
    assert a["capital_stock"] == 800, "회사 확장 계정은 한글 라벨(자본금)로 찾는다 — 새 라벨 파일 이름 형식에서도"
    assert a["interest_exp"] is None, "현금흐름 조정 항목('금융원가' 라벨)이 손익의 금융원가로 들어오면 안 된다"
    only_sep = {"CFS": [r for r in by["CFS"] if r["account_id"] != "ifrs-full_Assets"], "OFS": by["OFS"]}
    assert xbrl.pick(only_sep)[1] == "OFS", "연결에 자산총계가 없으면 별도로 넘어간다"


def test_gate_stops_on_timing_and_flags_units():
    """중단 위반은 멈추고, 단위 의심은 고치지 않고 검토 대상으로 뺀다 (docs/15 §4)."""
    from hup import checks
    T = pd.Timestamp("2021-03-20")
    df = pd.DataFrame({"corp_code": ["A", "A", "B"], "bsns_year": [2019, 2020, 2020],
                       "rcept_dt": [T - pd.Timedelta(365, "D"), T, T], "y": [0, 1, 0],
                       "_data_rcept": ["20200320", "20210320", "20210320"],
                       "_assets": [5e10, 5e7, 3e11], "_assets_prev": [np.nan, 5e10, 2.9e14],
                       "재무제표기준": ["CFS", "OFS", "CFS"]})
    ev = pd.DataFrame({"corp_code": ["A"], "event_date": [T + pd.Timedelta(100, "D")], "event_type": ["감사의견"]})
    assert not any(checks.hard_failures(df, ev).values())
    r = checks.review_flags(df)
    assert "10억" in r[1] and r[0] == "", "자산 5천만 원은 검토 대상"
    late = df.assign(_data_rcept=["20200320", "20210501", "20210320"])
    assert checks.hard_failures(late, ev)["재무 공개일 > 기준시점 T"] == 1
    assert checks.basis_switch(df).tolist() == [False, True, False]
    usd = df.assign(_통화=["KRW", "KRW", "USD"])
    assert "원화" in checks.review_flags(usd)[2], "원화가 아닌 통화는 검토 대상"
    # 단위 보정이 이미 고친 행은 전기값 불일치로 걸지 않는다 (v2.1)
    fixed = pd.DataFrame({"corp_code": ["D", "D"], "bsns_year": [2019, 2020], "_assets": [5e10, 6e10],
                          "_assets_raw": [5e13, 6e10], "_assets_prev": [np.nan, 5e10]})
    assert checks.review_flags(fixed).tolist() == ["", ""]
    dup = pd.concat([ev, ev])
    import tempfile
    from hup import config
    keep, config.RESULTS = config.RESULTS, Path(tempfile.mkdtemp())    # 검사 보고서를 저장소에 쓰지 않게
    try:
        checks.gate(df, dup)
    except checks.GateError:
        pass
    else:
        raise AssertionError("사건 중복이면 멈춰야 한다")
    finally:
        config.RESULTS = keep


def test_alert_threshold_is_lowest_score_meeting_precision():
    """경보 임계값 = 정밀도 30% 이상인 가장 낮은 점수 경계, 동점 묶음 중간에서 끊지 않는다 (docs/15 §6)."""
    y = np.array([1, 0, 1, 0, 0, 0, 0, 1, 0, 0])
    p = np.array([.9, .8, .7, .6, .5, .4, .4, .3, .2, .1])
    # 위에서부터 정밀도: 1, .5, .67, .5, .4, (0.4 묶음 끝) .286, .375, .333, .3
    assert model.threshold_at_precision(y, p, 0.30) == 0.1, "전부 경보해도 정확히 30%"
    assert model.threshold_at_precision(y, p, 0.35) == 0.3, "정밀도 35% 이상 중 가장 낮은 경계"
    assert model.threshold_at_precision(y, p, 0.99) == 0.9
    assert model.threshold_at_precision(np.zeros(5), np.arange(5.0), 0.3) is None


def test_original_audit_report_opinion():
    """최초 공시 원문의 감사보고서 의견 판정 — 검증에서 잡은 오판을 다시 내지 않는다 (docs/15 §11)."""
    from hup import dart
    clean = "독립된 감사인의 감사보고서 감사의견 우리의 의견으로는 공정하게 표시하고 있습니다. 감사의견근거 우리는 ..."
    assert dart.classify_audit_report(clean) == "적정"
    ic = clean + " 우리는 내부회계관리제도를 감사하였으며 감사보고서에서 부적정의견을 표명하였습니다."
    assert dart.classify_audit_report(ic) == "적정", "내부회계관리제도 부적정의견 언급을 재무제표 의견으로 읽으면 안 된다"
    disc = "감사보고서 우리는 별첨된 회사의 재무제표에 대하여 의견을 표명하지 않습니다. 의견거절근거 1. 감사범위 제한 ..."
    assert dart.classify_audit_report(disc) == "의견거절", "제목 없이 시작하는 의견거절"
    qual = "감사보고서 한정의견 우리의 의견으로는 ... 을 제외하고는 공정하게 표시하고 있습니다. 한정의견근거 ..."
    assert dart.classify_audit_report(qual) == "한정"
    old = "감사보고서 감사의견 ... 전기 재무제표에 대하여는 의견거절을 표명하였습니다. 우리의 의견으로는 공정하게 표시하고 있습니다."
    assert dart.classify_audit_report(old) == "적정", "전기 재무제표에 대한 의견 언급을 당기 의견으로 읽으면 안 된다"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\n전부 통과")
