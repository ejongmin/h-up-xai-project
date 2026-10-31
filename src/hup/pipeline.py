"""캐시 → 패널 → 라벨 → 학습 → 설명 카드. 중간 산출물은 CSV로 떨군다.

parquet 대신 CSV를 쓴다. 관측치가 2~3만 건이라 속도 차이가 무의미하고 의존성이 하나 준다.
"""
import numpy as np
import pandas as pd

from . import checks, config, dart, dataset, explain, features, labels, market, model, xbrl


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
    first = dart.first_filings(years) if config.FIN_SOURCE == "xbrl" else {}
    out = []
    for cc in corps:
        for y, info in uni.get(cc, {}).items():
            if config.FIN_SOURCE == "xbrl":
                # v2: 최초 접수번호의 원본 XBRL — T 에 실제로 공개된 값 (docs/15 §3)
                rc = first.get((cc, int(y)))
                blob = xbrl.fetch(rc[0]) if rc else None
                if blob is None:
                    out.append({"corp_code": cc, "bsns_year": int(y), "rcept_dt": info.get("rcept_dt"), "_원본없음": 1})
                    continue
                rows, fsdiv = xbrl.pick(xbrl.parse(blob, int(y))[0])
                for r in rows:
                    r["rcept_no"] = rc[0]
            else:
                rows, fsdiv = dart.financials(cc, int(y))
            if not rows:
                continue
            # 기준시점은 최초 접수일. 재무제표 응답의 rcept_no 는 정정본일 수 있다.
            dt = info.get("rcept_dt") or _rcept_dt(rows)
            if not dt:
                continue
            data_dt = max((r.get("rcept_no") or "")[:8] for r in rows)
            if config.FIN_SOURCE == "xbrl" and data_dt > dt:
                # 접수번호 날짜가 목록 접수일보다 늦다 (2026-10-31 실측 3건, docs/15 §3-1). 두 경우를 가른다.
                #  - 원문으로 최초 공개 자료임을 확인한 사례(config.FIRST_FILING_CONFIRMED) → T 그대로
                #  - 그 밖: 최초 공개 시점의 값인지 확인할 수 없다. 주 분석에서 빼고 따로 남긴다
                #    (T 를 늦추면 '최초 공시 시점의 예측'과 다른 문제가 된다)
                # 자정 넘김 예외는 원문을 확인한 사례에만 적용한다 — 하루 차이를 자동으로 허용하지 않는다 (docs/15 §3-1)
                if (cc, int(y), rc[0]) in config.FIRST_FILING_CONFIRMED:
                    data_dt = dt
                else:
                    checks.TIME_UNCONFIRMED.append({"corp_code": cc, "bsns_year": int(y), "목록접수일": dt, "접수번호": rc[0]})
                    continue
            a = features.extract(rows)
            if features.empty_statement(a):
                a = {k: None for k in a}
            r = features.ratios(a)
            ao = labels.current_period(dart.audit_opinion(cc, int(y)))
            r["감사의견판정"] = ("응답없음" if ao is None
                              else labels.classify_opinion(ao.get("adt_opinion")))
            r.update(corp_code=cc, bsns_year=int(y), rcept_dt=dt,
                     재무제표기준=fsdiv,          # CFS(연결) / OFS(별도) — 비율 수준이 달라진다
                     제출기한연장=float((cc, int(y)) in ext),
                     _revenue=a["revenue"], _assets=a["assets"],
                     _assets_prev=features.extract(rows, "frmtrm_amount")["assets"],
                     # API 는 최신 정정본을 준다. 데이터의 실제 접수일이 T 보다 늦으면 T 이후 정보일 수 있다 (docs/13 §8-3)
                     _data_rcept=data_dt)
            out.append(r)
    df = pd.DataFrame(out)
    if "_원본없음" in df:       # 원본 XBRL 이 없는 행은 패널에서 빼고 검사 보고서에 수를 남긴다 (docs/15 §3-3)
        checks.NO_SOURCE[:] = df.loc[df["_원본없음"] == 1, ["corp_code", "bsns_year"]].to_dict("records")
        df = df[df["_원본없음"] != 1].drop(columns="_원본없음")
    df["rcept_dt"] = pd.to_datetime(df["rcept_dt"], format="%Y%m%d", errors="coerce")
    df["정정본재무"] = (pd.to_datetime(df["_data_rcept"], format="%Y%m%d", errors="coerce") > df["rcept_dt"]).astype(int)
    df, fixes = features.fix_units(df.dropna(subset=["rcept_dt"]))
    out_ = config.RESULTS / "data_fix"; out_.mkdir(parents=True, exist_ok=True)
    fixes.to_csv(out_ / "단위수정_내역.csv", index=False, encoding="utf-8-sig")
    return features.add_changes(df)


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
    m = meta()
    corps = None
    if config.FIN_SOURCE == "xbrl":
        # 제외 규칙은 전부 기업 단위다. 원본 XBRL 은 남을 기업 것만 받는다 (금융업 등의 호출을 아낀다)
        stub = m[["corp_code"]].assign(bsns_year=0)
        corps = dataset.apply_exclusions(stub, m)[0]["corp_code"].tolist()
    kept, dropped = dataset.apply_exclusions(panel(corps), m)
    corps = kept["corp_code"].unique().tolist()
    ev = labels.build(corps, config.YEARS, "20150101", "20261231", include_secondary)

    df = dataset.attach_labels(kept, ev, horizon)
    df = dataset.mark_prior_events(df, ev)
    if config.VERSION == "v2":
        df = checks.gate(df, ev, horizon)          # 검사를 통과해야 저장·학습된다 (docs/15 §4)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.PROCESSED / "dataset.csv", index=False)
    dropped.to_csv(config.PROCESSED / "excluded.csv", index=False)
    ev.to_csv(config.PROCESSED / "events.csv", index=False)

    _write_manifest(df)

    sens = {}
    for h in config.HORIZON_SENSITIVITY:
        d = dataset.mark_prior_events(dataset.attach_labels(kept, ev, horizon_days=h), ev)
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


def _prepare(df, seed=42, horizon=None):
    """시점 분할 → 학습 구간에서만 정제 기준 산출. 모든 비교가 같은 분할을 쓴다.
    horizon: 그 데이터셋의 라벨 창(일). 엠바고가 창 길이를 따른다 (docs/13 §8-7)."""
    if "검토필요" in df:     # v2: 검토 대상 행은 판정 전까지 학습·평가에서 뺀다 (docs/15 §4)
        df = df[df["검토필요"] == 0]
    s = dataset.split(df, horizon_days=horizon)
    report = dataset.sanity(s, horizon)
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
            scores[f"{name}/{part}"] = model.evaluate(s[part]["y"], p, groups=s[part]["corp_code"])
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
    # 안정 변수를 **전부** 넘긴다. 상위 10개만 넘기면 그 10개가 기여도 순이라
    # 위험 상위 기업에서는 전부 위험을 올리는 쪽이고, '위험을 낮춘 요인'이 늘 비게 된다.
    # 상위 4개·하위 2개 선정은 card() 가 한다.
    allow = explain.stable_features(lambda random_state: model.ensemble(random_state=random_state),
                                    res["splits"]["train"][use], res["splits"]["train"]["y"],
                                    top=len(use))
    ref = res["splits"]["train"][use].median()
    p = cal.predict_proba(X)[:, 1]          # 보여줄 확률
    rank = est.predict_proba(X)[:, 1]        # 상위 선정은 보정 전 순위로 (동점 방지)
    sv = explain.shap_values(est, X)
    # 카드에 찍는 '실측'은 **정제 전 원본**이어야 한다. 정제본은 1/99 분위로 클리핑돼
    # 극단 기업들이 전부 같은 값(경계값)을 갖는다 — 그걸 실측이라 적으면 거짓말이 된다.
    raw = load().set_index(["corp_code", "bsns_year"])
    out = []
    for i in np.argsort(-rank)[:n]:
        cc, by = s.iloc[i]["corp_code"], int(s.iloc[i]["bsns_year"])
        try:
            shown = raw.loc[(cc, by)]
            if hasattr(shown, "iloc") and getattr(shown, "ndim", 1) > 1:
                shown = shown.iloc[0]
        except KeyError:
            shown = X.iloc[i]
        top = [n for n, _ in pd.Series(sv[i], index=use).sort_values(ascending=False).items()
               if n in allow and not explain._card_excluded(n)][:6]
        # 자본이 음(-)이면 자본 기반 비율은 반사실에서도 뺀다 (카드 본문과 같은 규칙)
        skip = explain.EQUITY_BASED if explain._equity_wiped(shown) else ()
        # 반사실도 **카드에 찍는 확률과 같은 보정 모형**으로 계산한다
        base, items = explain.counterfactual(cal, X.iloc[i], use, top, ref, skip=skip)
        out.append({"corp_code": cc, "bsns_year": by,
                    "y": int(y.iloc[i]), "prob": float(p[i]),
                    "card": explain.card(shown, sv[i], use, allow=allow, prob=float(p[i]),
                                         ref=ref, cf=explain.counterfactual_lines(base, items))})
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


def _write_manifest(df):
    """데이터셋 스냅샷 지문. 보고서 수치가 어느 데이터에서 나왔는지 대조하는 용도다.

    docs/99 에 "본문 수치마다 출처 커밋·데이터 스냅샷 표기"라고 써두고 하지 않았다.
    사람이 기억하는 대신 build 가 매번 남긴다.
    """
    import datetime as dt
    import hashlib
    import json
    import subprocess
    f = config.PROCESSED / "dataset.csv"
    h = hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.exists() else ""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
                                capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        commit = ""
    m = {
        "생성": dt.datetime.now().isoformat(timespec="seconds"),
        "커밋": commit,
        "dataset.csv sha256(16)": h,
        "관측치": int(len(df)),
        "사건": int(df["y"].sum()),
        "사건비율": round(float(df["y"].mean()), 4),
        "예측창": config.HORIZON_DAYS,
        "분할": {k: list(v) for k, v in config.SPLIT.items()},
    }
    (config.PROCESSED / "MANIFEST.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2))
    return m
