"""캐시 → 패널 → 라벨 → 학습 → 설명 카드. 중간 산출물은 CSV로 떨군다.

parquet 대신 CSV를 쓴다. 관측치가 2~3만 건이라 속도 차이가 무의미하고 의존성이 하나 준다.
"""
import numpy as np
import pandas as pd

from . import config, dart, dataset, explain, features, labels, market, model


def uni_years(uni):
    return {int(y) for v in uni.values() for y in v} or {2015}


def _rcept_dt(rows):
    """응답 행의 rcept_no 앞 8자리가 접수일자다. 공시검색을 따로 돌 필요가 없다."""
    for r in rows:
        no = r.get("rcept_no") or ""
        if len(no) >= 8:
            return no[:8]
    return None


# 재무제표에는 없고 공시 행태에만 있는 신호. 기본 모델에는 넣지 않는다
# (계획서 범위가 '재무제표 기반'이므로). 13주차 추가 변수 실험의 후보군이다.
DISCLOSURE_COLS = ["제출기한연장"]


def panel(corp_codes=None, years=None):
    """기업-연도 패널. 재무제표 캐시만 읽으므로 수집이 끝난 뒤에는 API를 안 탄다."""
    uni = dart.universe(years)
    corps = corp_codes or sorted(uni)
    # 제출기한 연장신고는 그 사업연도 보고서보다 **먼저** 접수된다.
    # 따라서 기준시점 T 에 이미 공개돼 있다 — 시차 없이 그대로 쓸 수 있다.
    ext = dart.extension_filers(range(min(uni_years(uni)), max(uni_years(uni)) + 3))
    out = []
    for cc in corps:
        for y, info in uni.get(cc, {}).items():
            rows, fsdiv = dart.financials(cc, int(y))
            if not rows:
                continue
            # 기준시점은 최초 접수일. 재무제표 응답의 rcept_no 는 정정본일 수 있다.
            dt = info.get("rcept_dt") or _rcept_dt(rows)
            if not dt:
                continue
            a = features.extract(rows)
            r = features.ratios(a)
            ao = labels.current_period(dart.audit_opinion(cc, int(y)))
            r["감사의견판정"] = ("응답없음" if ao is None
                              else labels.classify_opinion(ao.get("adt_opinion")))
            r.update(corp_code=cc, bsns_year=int(y), rcept_dt=dt,
                     재무제표기준=fsdiv,          # CFS(연결) / OFS(별도) — 비율 수준이 달라진다
                     제출기한연장=float((cc, int(y)) in ext),
                     _revenue=a["revenue"], _assets=a["assets"])
            out.append(r)
    df = pd.DataFrame(out)
    df["rcept_dt"] = pd.to_datetime(df["rcept_dt"], format="%Y%m%d", errors="coerce")
    return features.add_changes(df.dropna(subset=["rcept_dt"]))


def meta(corp_codes=None):
    """제외 규칙에 필요한 업종코드·결산월."""
    corps = corp_codes or sorted(dart.universe())
    name = {r["corp_code"]: r["corp_name"] for r in dart.corp_codes()}
    rows = []
    for cc in corps:
        c = dart.company(cc)
        rows.append({"corp_code": cc, "corp_name": name.get(cc, ""),
                     "induty_code": c.get("induty_code", ""), "acc_mt": c.get("acc_mt", "")})
    return pd.DataFrame(rows)


def build(horizon=None, include_secondary=False):
    """패널 + 제외 + 라벨 → data/processed/dataset.csv

    패널과 사건 목록은 **한 번만** 만들고 창 길이만 바꿔 라벨을 다시 붙인다.
    창마다 처음부터 다시 만들면 캐시 2만여 건을 네 번 읽게 된다.
    """
    kept, dropped = dataset.apply_exclusions(panel(), meta())
    corps = kept["corp_code"].unique().tolist()
    ev = labels.build(corps, config.YEARS, "20150101", "20261231", include_secondary)

    df = dataset.attach_labels(kept, ev, horizon)
    df.to_csv(config.PROCESSED / "dataset.csv", index=False)
    dropped.to_csv(config.PROCESSED / "excluded.csv", index=False)
    ev.to_csv(config.PROCESSED / "events.csv", index=False)

    sens = {}
    for h in config.HORIZON_SENSITIVITY:
        d = dataset.attach_labels(kept, ev, horizon_days=h)
        sens[h] = (int(d["y"].sum()), float(d["y"].mean()))
        if h != (horizon or config.HORIZON_DAYS):
            d.to_csv(config.PROCESSED / f"dataset_h{h}.csv", index=False)
    return df, sens, dropped, ev


def load(path=None):
    """corp_code 는 반드시 문자열로 읽는다.

    '00126380' 같은 8자리 고유번호라 기본 추론에 맡기면 정수 126380 이 되어
    앞자리 0 이 사라진다. DART 재조회·종목코드 매핑이 전부 조용히 실패한다.
    """
    return pd.read_csv(path or config.PROCESSED / "dataset.csv",
                       parse_dates=["rcept_dt"], dtype={"corp_code": str})


def _prepare(df, seed=42):
    """시점 분할 → 학습 구간에서만 정제 기준 산출. 모든 비교가 같은 분할을 쓴다."""
    s = dataset.split(df)
    report = dataset.sanity(s)
    fin = [c for c in features.FEATURE_COLS if c in df.columns]
    mkt = [c for c in market.COLS if c in df.columns]
    st = dataset.fit_clean(s["train"], cols=fin + mkt)
    s = {k: dataset.apply_clean(v, st) for k, v in s.items()}
    return s, report, fin, mkt


def _with_flags(s, cols):
    have = set(s["train"].columns)
    return cols + [f"{c}_결측" for c in cols if f"{c}_결측" in have]


def _fit_eval(s, use, seed=42, parts=("valid", "test")):
    fits, scores = {}, {}
    for name, est in (("로지스틱", model.baseline()), ("앙상블", model.ensemble(random_state=seed))):
        est.fit(s["train"][use], s["train"]["y"])
        fits[name] = est
        for part in parts:
            p = est.predict_proba(s[part][use])[:, 1]
            scores[f"{name}/{part}"] = model.evaluate(s[part]["y"], p)
    return fits, scores


def train(df=None, seed=42):
    df = load() if df is None else df
    s, report, fin, _ = _prepare(df, seed)
    use = _with_flags(s, fin)
    fits, scores = _fit_eval(s, use, seed)
    scores["기준선(사건비율)"] = {"PR-AUC": model.prevalence_baseline(s["test"]["y"])}
    return {"splits": s, "cols": use, "fits": fits, "scores": scores, "분할": report}


def compare(df=None, seed=42):
    """재무만 / 시장만 / 재무+시장. 분할·모델·정제 기준을 고정하고 변수 집합만 바꾼다.

    Shumway(2001)가 시장 변수 쪽이 낫다고 한 것이 국내 상장사·우리 라벨에서도
    맞는지 재는 실험이다. 답이 어느 쪽이든 그대로 보고한다.
    """
    df = load() if df is None else df
    s, report, fin, mkt = _prepare(df, seed)
    if not mkt:
        raise RuntimeError("시장 변수 열이 없다. market.attach() 를 먼저 돌릴 것")
    sets = {"재무만": fin, "시장만": mkt, "재무+시장": fin + mkt}
    out = {"분할": report, "기준선": model.prevalence_baseline(s["test"]["y"]), "결과": {}}
    for name, cols in sets.items():
        _, sc = _fit_eval(s, _with_flags(s, cols), seed, parts=("valid",))
        out["결과"][name] = sc
    return out


def cards(res, n=5, part="test"):
    """위험 상위 n건의 설명 카드. 안정 변수만 올린다."""
    s, use, est = res["splits"][part], res["cols"], res["fits"]["앙상블"]
    X, y = s[use], s["y"]
    # 카드에 찍는 확률은 **보정된 모형**에서 뽑는다. 보정 전 앙상블은 평균 예측이
    # 실제 사건비율의 7.6배로 나온다(2026-09-04 검증구간: 0.2048 vs 0.0268).
    # SHAP 은 보정 전 모형으로 계산한다 — 보정은 단조변환이라 방향이 바뀌지 않고,
    # 트리 구조가 있어야 TreeExplainer 가 돈다.
    cal = model.calibrated(model.ensemble, "isotonic")
    cal.fit(res["splits"]["train"][use], res["splits"]["train"]["y"])
    allow = explain.stable_features(lambda random_state: model.ensemble(random_state=random_state),
                                    res["splits"]["train"][use], res["splits"]["train"]["y"])
    ref = res["splits"]["train"][use].median()
    p = cal.predict_proba(X)[:, 1]          # 보여줄 확률
    rank = est.predict_proba(X)[:, 1]        # 상위 선정은 보정 전 순위로 (동점 방지)
    sv = explain.shap_values(est, X)
    out = []
    for i in np.argsort(-rank)[:n]:
        out.append({"corp_code": s.iloc[i]["corp_code"], "bsns_year": int(s.iloc[i]["bsns_year"]),
                    "y": int(y.iloc[i]), "prob": float(p[i]),
                    "card": explain.card(X.iloc[i], sv[i], use, allow=allow, prob=float(p[i]),
                                         ref=ref)})
    return out, allow


def label_loss_by_extension(df, uni, horizon=None):
    """A-2 진단: 12개월 창에서 놓치는 사건이 무작위인가.

    사업보고서 제출 간격이 창을 넘으면 사건이 어느 행에도 안 붙는다(docs/01 부록 A-2).
    그 손실이 '제출기한을 연장한 기업'에 쏠려 있다면 손실은 무작위가 아니고,
    하필 부실 직전 기업의 사건이 사라지고 있다는 뜻이다.

    반환: 제출간격 분포와 연장 여부별 창 초과 비율.
    """
    h = horizon or config.HORIZON_DAYS
    rows = []
    for cc, ys in uni.items():
        seq = sorted((int(y), pd.Timestamp(v["rcept_dt"])) for y, v in ys.items())
        for (y0, t0), (y1, t1) in zip(seq, seq[1:]):
            # 간격을 늘리는 것은 **뒤쪽(t1) 보고서가 늦는 것**이다.
            # 연장 플래그를 y0 에 붙이면 방향이 거꾸로다 — 그 해 보고서가 늦으면
            # 오히려 다음 보고서까지 간격이 짧아진다. 그래서 y1 에 맞춘다.
            rows.append({"corp_code": cc, "bsns_year": y0, "다음연도": y1,
                         "제출간격": (t1 - t0).days, "창초과": int((t1 - t0).days > h)})
    gap = pd.DataFrame(rows)
    if "제출기한연장" in df.columns:
        ext = df[["corp_code", "bsns_year", "제출기한연장"]].rename(
            columns={"bsns_year": "다음연도"})
        gap = gap.merge(ext, on=["corp_code", "다음연도"], how="left")
        by = gap.groupby(gap["제출기한연장"].fillna(0))["창초과"].agg(["mean", "size"])
    else:
        by = None
    return {"제출간격_중앙값": float(gap["제출간격"].median()),
            "창초과_건수": int(gap["창초과"].sum()),
            "창초과_비율": float(gap["창초과"].mean()),
            "연장여부별_창초과율": by}
