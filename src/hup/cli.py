"""단계별 실행.  python -m hup.cli <단계>

수집은 며칠에 걸쳐 돈다. 한도에 걸리면 멈추되 캐시는 남으므로 다음 날 다시 치면 이어진다.
"""
import sys

from . import config, dart


def corp():
    print(f"상장사 {len(dart.corp_codes())}개 → data/raw/corp_codes.json")


def fs():
    """python -m hup.cli fs [샤드/전체]   예: fs 0/2, fs 1/2

    키가 여러 개일 때 담당을 나눈다. 인터리브(i % n)로 자르는 이유는,
    corp_code 순으로 반씩 자르면 오래된 기업(연도 수가 많은 쪽)이 한 프로세스에 몰려
    한쪽만 먼저 끝나기 때문이다.

    캐시는 crtfc_key 를 키에 넣지 않으므로 두 프로세스가 공유한다.
    담당이 겹치지 않으면 같은 캐시 파일을 동시에 쓸 일도 없다.
    """
    shard, nshard = 0, 1
    if len(sys.argv) > 2 and "/" in sys.argv[2]:
        shard, nshard = (int(x) for x in sys.argv[2].split("/"))
    uni = dart.universe()
    corps = [c for i, c in enumerate(sorted(uni)) if i % nshard == shard]
    total = sum(len(uni[c]) for c in corps) * 2
    print(f"[샤드 {shard}/{nshard}] 대상 {len(corps)}사 / "
          f"기업-연도 {total//2}건 / 예상 호출 {total:,}건", flush=True)
    n = 0
    try:
        for i, cc in enumerate(corps):
            dart.company(cc)
            for y in uni[cc]:
                dart.financials(cc, int(y))
                dart.audit_opinion(cc, int(y))
                n += 2
            if i % 100 == 0:
                print(f"  [{shard}/{nshard}] {i}/{len(corps)}  "
                      f"실호출 {dart.CALLS:,}/20,000  (순회 {n:,})", flush=True)
    except dart.QuotaExceeded as e:
        print(f"{e}\n여기까지 {n:,}건. 내일 같은 명령을 다시 실행하면 이어서 받는다.")
        return
    print(f"수집 완료 {n:,}건")


def probe():
    """표본으로 계정 매핑 성공률을 먼저 잰다 (2주차 산출물).

    전체 수집 전에 돌린다. 여기서 실패율이 높으면 매핑 표를 고쳐야 하고,
    데이터가 다 쌓인 뒤에 발견하면 며칠치 할당량을 다시 써야 한다.
    """
    import random
    import pandas as pd
    from . import features
    corps = dart.corp_codes()
    random.seed(0)
    sample = random.sample(corps, 100)
    years = (2022, 2023)

    got, rows = 0, []
    for c in sample:
        for y in years:
            fs, _ = dart.financials(c["corp_code"], y)
            if not fs:
                continue
            got += 1
            a = features.extract(fs)
            rows.append({k: (v is not None) for k, v in a.items()})
    df = pd.DataFrame(rows)
    print(f"표본 {len(sample)}사 × {len(years)}년 = {len(sample)*len(years)}건 요청")
    print(f"재무제표 응답 있음: {got}건 ({got/(len(sample)*len(years)):.0%})\n")
    print("계정별 매핑 성공률 (응답 있는 건 기준)")
    for k, v in df.mean().sort_values().items():
        mark = "  <-- 확인 필요" if v < 0.8 else ""
        print(f"  {k:14s} {v:6.1%}{mark}")


def dryrun():
    """수집이 끝나기 전에, **이미 캐시된 기업만으로** 파이프라인을 끝까지 통과시킨다.

    목적은 결과가 아니라 배선 검증이다. 합성 데이터로는 안 잡히는 문제가
    실응답에서 계속 나왔으므로, 라벨·제외·분할 구간도 실데이터로 한 번 돌려본다.
    """
    from . import config, dataset, labels, pipeline

    uni = dart.universe()
    cached = {f.name.split("corp_code-")[1][:8]
              for f in config.CACHE.glob("fnlttSinglAcntAll*") if "corp_code-" in f.name}
    corps = sorted(set(uni) & cached)
    print(f"캐시된 기업 {len(corps)}사 (전체 {len(uni)}사 중 {len(corps)/len(uni):.0%})\n")
    if len(corps) < 50:
        print("표본이 너무 적다. 수집을 더 기다릴 것.")
        return

    pn = pipeline.panel(corp_codes=corps)
    print(f"패널 {len(pn):,}행  결측 아닌 부채비율 {pn['부채비율'].notna().mean():.1%}")

    kept, dropped = dataset.apply_exclusions(pn, pipeline.meta(corps))
    print(f"제외 {len(dropped):,}행 → {dict(dropped['_excl'].value_counts())}")
    print(f"남은 관측치 {len(kept):,}행")

    ev = labels.build(corps, config.YEARS, "20150101", "20261231")
    print(f"\n사건 {len(ev):,}건  유형별 {dict(ev['event_type'].value_counts())}")
    print("연도별:", dict(sorted(ev['event_date'].dt.year.value_counts().items())))

    for h in config.HORIZON_SENSITIVITY:
        d = dataset.attach_labels(kept, ev, horizon_days=h)
        print(f"  창 {h}일 → 사건 라벨 {int(d['y'].sum()):,}건 ({d['y'].mean():.2%})")

    d = dataset.attach_labels(kept, ev)
    print("\n분할:", dataset.sanity(dataset.split(d)))
    diag = pipeline.label_loss_by_extension(d, {c: uni[c] for c in corps})
    print(f"제출간격 중앙값 {diag['제출간격_중앙값']:.0f}일 / "
          f"창 초과 {diag['창초과_건수']:,}건 ({diag['창초과_비율']:.1%})")
    print("연장여부별 창 초과율:\n", diag["연장여부별_창초과율"])


def build():
    from . import pipeline
    df, sens, dropped, ev = pipeline.build()
    print(f"주 분석 창 {config.HORIZON_DAYS}일")
    print(f"관측치 {len(df):,}건 / 사건 {int(df['y'].sum()):,}건 ({df['y'].mean():.2%})")
    print(f"제외 {len(dropped):,}건 {dict(dropped['_excl'].value_counts())}")
    print(f"사건 원천 {len(ev):,}건 {dict(ev['event_type'].value_counts())}")
    print("\n창 민감도")
    for h, (n, rate) in sens.items():
        mark = "  <- 주 분석" if h == config.HORIZON_DAYS else ""
        print(f"  {h}일 → 사건 {n:,}건 ({rate:.2%}){mark}")
    print("\n저장: data/processed/dataset.csv (+ 민감도별 dataset_h*.csv)")


def tables():
    """4주차 산출물: 표본 구성표 · 결측률 표 · 감사의견 불명 민감도."""
    import pandas as pd
    from . import config, pipeline, features
    pd.set_option("display.width", 200)
    df = pipeline.load()
    out = config.RESULTS / "w04"
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 68)
    print("[1] 표본 구성표 (연도 × 사건/정상)")
    t = (df.assign(연도=df.rcept_dt.dt.year).groupby("연도")["y"]
           .agg(관측치="size", 사건="sum", 사건비율="mean"))
    t["사건비율"] = t["사건비율"].round(4)
    print(t.to_string())
    t.to_csv(out / "표본구성표.csv")

    excl = pd.read_csv(config.PROCESSED / "excluded.csv")
    print("\n제외 사유별:", dict(excl["_excl"].value_counts()))

    print("\n" + "=" * 68)
    print("[2] 결측률 — 변수별 (상위 12개)")
    cols = [c for c in features.FEATURE_COLS if c in df.columns]
    miss = df[cols].isna().mean().sort_values(ascending=False)
    print((miss.head(12) * 100).round(2).to_string())
    miss.to_csv(out / "결측률_변수별.csv")

    print("\n결측률 — 사건군 vs 정상군 (차이 큰 순 6개)")
    g = df.groupby("y")[cols].apply(lambda d: d.isna().mean()).T
    g.columns = ["정상", "사건"]
    g["차이"] = g["사건"] - g["정상"]
    print((g.sort_values("차이", ascending=False).head(6) * 100).round(2).to_string())
    g.to_csv(out / "결측률_사건군비교.csv")

    print("\n" + "=" * 68)
    print("[3] 감사의견 '불명' 민감도")
    if "감사의견판정" not in df.columns:
        print("  감사의견판정 컬럼이 없다. `build` 를 다시 돌릴 것")
        return
    vc = df["감사의견판정"].value_counts()
    print("판정 분포:", dict(vc), f"| 불명 비율 {(df['감사의견판정'].isin(['불명','응답없음'])).mean():.2%}")

    unk = df["감사의견판정"].isin(["불명", "응답없음"])
    print(f"\n불명 기업-연도의 사건 발생률 {df.loc[unk,'y'].mean():.4f} "
          f"vs 판정 있음 {df.loc[~unk,'y'].mean():.4f}")
    print("\n불명 비율 — 연도별")
    print((df.assign(연도=df.rcept_dt.dt.year).groupby("연도")["감사의견판정"]
             .apply(lambda s: s.isin(["불명", "응답없음"]).mean()) * 100).round(1).to_string())

    print("\n(a) 불명을 정상으로 (현행) vs (b) 불명 제외 — 검증 구간")
    for name, d in [("(a) 현행", df), ("(b) 불명 제외", df[~unk])]:
        s2, rep, fin, _ = pipeline._prepare(d)
        m = pipeline._fit_eval(s2, pipeline._with_flags(s2, fin), parts=("valid",))[1]["앙상블/valid"]
        print(f"  {name:<12} n={rep['valid']['n']:,} 사건={rep['valid']['사건']} "
              f"PR-AUC {m['PR-AUC']:.4f} {m['PR-AUC_95CI']}")
    print(f"\n저장: {out}")


def eda():
    """6주차: 탐색적 분석. 질문 네 개에 답하는 것 외에는 그리지 않는다.

      1. 부실 신호는 언제부터 보이는가 (사건 전 3년 궤적)
      2. 수준값과 변화량 중 무엇이 더 잘 가르는가
      3. 사건이 특정 연도·업종·규모에 몰려 있는가
      4. 변수끼리 얼마나 겹치는가 (7주차 부호 반전의 원인)
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from . import config, features, pipeline
    plt.rcParams["font.family"] = ["AppleGothic", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    from . import dataset
    raw = pipeline.load()
    raw = raw[raw.rcept_dt.dt.year <= 2025]       # 2026 은 우측 절단
    out = config.RESULTS / "eda"; out.mkdir(parents=True, exist_ok=True)
    cols = [c for c in features.FEATURE_COLS if c in raw.columns]
    # 상관·판별력은 **모델이 실제로 보는 정제 후 데이터**로 잰다.
    # 원본으로 재면 이상치 몇 건이 상관을 지배해 r=0.998 같은 값이 나온다.
    st = dataset.fit_clean(raw[raw.rcept_dt.dt.year <= 2022], cols=cols)
    df = dataset.apply_clean(raw, st, add_missing_flags=False)

    print("=" * 68)
    print("[1] 사건 전 궤적 — 사건 시점 t 기준 t-1/t-2/t-3 의 중앙값 (정제 후)")
    ev = df[df.y == 1][["corp_code", "bsns_year"]].rename(columns={"bsns_year": "t"})
    keep = ["부채비율", "유동비율", "이자보상배율", "영업이익률", "ROA", "영업현금흐름_매출"]
    traj = {}
    for lag in (0, 1, 2):
        m = ev.assign(bsns_year=ev.t - lag).merge(df, on=["corp_code", "bsns_year"])
        traj[f"t-{lag+1}"] = m[keep].median()
    traj["정상군"] = df[df.y == 0][keep].median()
    tr = pd.DataFrame(traj)[["t-3", "t-2", "t-1", "정상군"]]
    print(tr.round(3).to_string())
    tr.to_csv(out / "사건전_궤적.csv")

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, c in zip(axes.ravel(), keep):
        ax.plot([-3, -2, -1], [tr.loc[c, "t-3"], tr.loc[c, "t-2"], tr.loc[c, "t-1"]],
                marker="o", label="사건군")
        ax.axhline(tr.loc[c, "정상군"], ls="--", color="gray", label="정상군")
        ax.set_title(c); ax.set_xticks([-3, -2, -1]); ax.legend(fontsize=8)
    fig.suptitle("사건 전 3년 궤적 (중앙값)"); fig.tight_layout()
    fig.savefig(out / "사건전_궤적.png", dpi=120); plt.close(fig)

    print("\n" + "=" * 68)
    print("[2] 수준값 vs 변화량 — 사건/정상 중앙값 차이가 큰 변수 (표준화 차이)")
    d = df[cols + ["y"]].copy()
    sd = d[cols].std()
    diff = ((d[d.y == 1][cols].median() - d[d.y == 0][cols].median()) / sd).abs()
    diff = diff.sort_values(ascending=False)
    lv = [c for c in diff.index if not c.startswith("Δ") and not c.endswith("증가율")]
    ch = [c for c in diff.index if c.startswith("Δ") or c.endswith("증가율")]
    print("수준값 상위 6:"); print(diff[lv].head(6).round(3).to_string())
    print("변화량 상위 4:"); print(diff[ch].head(4).round(3).to_string())
    diff.to_csv(out / "판별력_표준화차이.csv")

    print("\n" + "=" * 68)
    print("[3] 사건 쏠림")
    print("규모 5분위별 사건비율 (로그자산 기준)")
    q = pd.qcut(df["로그자산"], 5, labels=["최소", "소", "중", "대", "최대"])
    print((df.groupby(q, observed=True)["y"].agg(["size", "mean"])
             .rename(columns={"size": "n", "mean": "사건비율"}).round(4)).to_string())
    if "재무제표기준" in df.columns:
        print("\n연결/별도별 사건비율")
        print(df.groupby("재무제표기준")["y"].agg(["size", "mean"]).round(4).to_string())

    print("\n" + "=" * 68)
    print("[4] 다중공선성 — 상관 |r| >= 0.7 인 쌍 (정제 후 기준)")
    corr = df[cols].corr().abs()
    pairs = [(corr.index[i], corr.columns[j], corr.iat[i, j])
             for i in range(len(cols)) for j in range(i + 1, len(cols))
             if corr.iat[i, j] >= 0.7]
    for a_, b_, r in sorted(pairs, key=lambda x: -x[2]):
        print(f"  {a_:<18} {b_:<18} r={r:.3f}")
    if not pairs:
        print("  없음")
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(df[cols].corr(), cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=90, fontsize=7)
    ax.set_yticks(range(len(cols))); ax.set_yticklabels(cols, fontsize=7)
    fig.colorbar(im); fig.tight_layout()
    fig.savefig(out / "상관행렬.png", dpi=120); plt.close(fig)
    print(f"\n저장: {out}")


def train():
    from . import pipeline
    res = pipeline.train()
    print(res["분할"])
    for k, v in res["scores"].items():
        print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})


def diagnose():
    """7주차 남은 항목: 공선성(VIF) · 축소 변수셋 부호 · Shumway 군집 표준오차.

    전부 **학습·검증 구간에서만** 한다. 평가 구간은 열지 않는다.
    """
    import numpy as np
    import pandas as pd
    from . import config, dataset, model, pipeline
    df = pipeline.load()
    s_, rep, fin, _ = pipeline._prepare(df)
    tr = s_["train"]
    X = tr[fin].astype(float)

    print("=" * 68)
    print("[1] VIF (분산팽창계수) — 10 이상이면 공선성 문제")
    Xc = X.loc[:, X.std() > 0]
    corr = np.corrcoef(Xc.values, rowvar=False)
    vif = pd.Series(np.diag(np.linalg.pinv(corr)), index=Xc.columns).sort_values(ascending=False)
    print(vif.head(12).round(2).to_string())

    print("\n" + "=" * 68)
    print("[2] 축소 변수셋 — 상관 군집마다 하나만 남기고 부호 재확인")
    drop = ["순이익률", "영업현금흐름_매출", "총자산영업이익률", "자기자본비율", "영업손실"]
    keep = [c for c in fin if c not in drop]
    print(f"제외: {drop}")
    expect = {"부채비율": "+", "자본잠식": "+", "완전자본잠식": "+", "자본잠식률": "+",
              "2년연속영업손실": "+", "Δ부채비율": "+", "유동비율": "-", "이자보상배율": "-",
              "영업이익률": "-", "ROA": "-", "영업현금흐름_부채": "-",
              "매출증가율": "-", "로그자산": "-"}
    for name, cols in [("전체 27개", fin), ("축소셋", keep)]:
        st = dataset.fit_clean(tr, cols=cols)
        Xa = dataset.apply_clean(tr, st, add_missing_flags=False)[cols]
        lr = model.baseline().fit(Xa, tr["y"])
        co = pd.Series(lr.named_steps["clf"].coef_[0], index=cols)
        ok = sum(1 for v, e in expect.items() if v in co and
                 (("+" if co[v] > 0 else "-") == e))
        tot = sum(1 for v in expect if v in co)
        bad = [v for v, e in expect.items() if v in co and ("+" if co[v] > 0 else "-") != e]
        print(f"  {name:<10} 부호 일치 {ok}/{tot}   어긋남: {bad}")

    print("\n" + "=" * 68)
    print("[3] Shumway(2001) 군집 보정 — 같은 기업의 여러 연도는 독립이 아니다")
    n_obs = len(tr)
    n_firm = tr["corp_code"].nunique()
    avg = n_obs / n_firm
    print(f"학습 구간 관측치 {n_obs:,} / 기업 {n_firm:,} → 기업당 평균 {avg:.2f}년")
    print(f"Shumway 보정: 검정통계량을 √{avg:.2f} = {np.sqrt(avg):.2f} 로 나눈다")
    st = dataset.fit_clean(tr, cols=fin)
    Xa = dataset.apply_clean(tr, st, add_missing_flags=False)[fin]
    lr = model.baseline().fit(Xa, tr["y"])
    co = lr.named_steps["clf"].coef_[0]
    # 표준오차: 로지스틱 정보행렬의 대각 (표준화된 X 기준)
    Z = lr.named_steps["scale"].transform(lr.named_steps["impute"].transform(Xa))
    pr = lr.predict_proba(Xa)[:, 1]
    W = pr * (1 - pr)
    cov = np.linalg.pinv((Z * W[:, None]).T @ Z)
    se = np.sqrt(np.diag(cov))
    z_naive = co / se
    z_adj = z_naive / np.sqrt(avg)
    out = pd.DataFrame({"계수": co, "z_보정전": z_naive, "z_보정후": z_adj}, index=fin)
    out["유의_보정전"] = np.abs(out.z_보정전) > 1.96
    out["유의_보정후"] = np.abs(out.z_보정후) > 1.96
    print(f"\n유의 변수: 보정 전 {out.유의_보정전.sum()}개 → 보정 후 {out.유의_보정후.sum()}개")
    print(out.reindex(out.z_보정후.abs().sort_values(ascending=False).index)
             .head(10).round(3).to_string())
    (config.RESULTS / "w07").mkdir(parents=True, exist_ok=True)
    out.to_csv(config.RESULTS / "w07" / "계수_군집보정.csv")
    vif.to_csv(config.RESULTS / "w07" / "vif.csv")
    print(f"\n저장: {config.RESULTS / 'w07'}")


def calibrate():
    """확률 보정 비교. **검증 구간에서만 판단한다** — 평가 구간은 열지 않는다."""
    from . import model, pipeline
    df = pipeline.load()
    s, rep, fin, _ = pipeline._prepare(df)
    use = pipeline._with_flags(s, fin)
    Xtr, ytr = s["train"][use], s["train"]["y"]
    Xva, yva = s["valid"][use], s["valid"]["y"]

    cands = {
        "앙상블 (balanced, 보정없음)": model.ensemble(),
        "앙상블 + isotonic":          model.calibrated(model.ensemble, "isotonic"),
        "앙상블 + sigmoid":           model.calibrated(model.ensemble, "sigmoid"),
        "앙상블 (가중없음) + isotonic": model.calibrated(
            lambda **k: model.ensemble(class_weight=None, **k), "isotonic"),
    }
    print(f"검증 구간 n={len(yva):,} 사건={int(yva.sum())} 실제비율={yva.mean():.4f}\n")
    best = None
    for name, est in cands.items():
        est.fit(Xtr, ytr)
        p = est.predict_proba(Xva)[:, 1]
        m = model.evaluate(yva, p, n_boot=300)
        print(f"{name}")
        print(f"   Brier {m['Brier']:.4f}  PR-AUC {m['PR-AUC']:.4f} {m['PR-AUC_95CI']}  "
              f"예측확률 평균 {p.mean():.4f}")
        if best is None or m["Brier"] < best[1]:
            best = (name, m["Brier"], p)
    print(f"\n최저 Brier: {best[0]}\n")
    print("보정 후 확률 구간별 실제 발생률 (검증 구간)")
    print(model.calibration_table(yva, best[2]).to_string())


def prices():
    """시세 → 시장변수 3종을 데이터셋에 붙인다 (dataset_mkt.csv)."""
    from . import config, dart, market, pipeline
    df = pipeline.load()
    tick = {r["corp_code"]: r["stock_code"] for r in dart.corp_codes() if r.get("stock_code")}
    out = market.attach(df, tick)
    have = out[market.COLS].notna().all(axis=1).mean()
    print(f"시장변수 4종 모두 확보한 행 {have:.1%} ({len(out):,}행 중)")
    for c in market.COLS:
        print(f"  {c:<12} 결측 {out[c].isna().mean():.1%}")
    out.to_csv(config.PROCESSED / "dataset_mkt.csv", index=False)
    print("저장: data/processed/dataset_mkt.csv")


def compare():
    """재무만 / 시장만 / 재무+시장 — **검증 구간에서만 판단**."""
    from . import config, pipeline
    f = config.PROCESSED / "dataset_mkt.csv"
    if not f.exists():
        print("먼저 `python -m hup.cli prices` 를 돌릴 것"); return
    df = pipeline.load(f)
    r = pipeline.compare(df)
    print(f"검증 구간 기준선(사건비율) {r['분할']['valid']['사건비율']:.4f}\n")
    for name, sc in r["결과"].items():
        v = sc["앙상블/valid"]
        print(f"  {name:<10} PR-AUC {v['PR-AUC']:.4f} {v['PR-AUC_95CI']}  "
              f"재현율@정밀도0.3 {v['재현율@정밀도0.3']:.3f}")


def w08():
    """8주차: 매칭 학습 + 전수 평가 · 불균형 3안 · 그룹분할/중복제거 민감도.

    **전부 검증 구간에서 판단한다.** 평가 구간은 최종 모델 확정 후 1회.
    """
    import pandas as pd
    from . import model, pipeline
    df = pipeline.load()
    s_, rep, fin, _ = pipeline._prepare(df)
    use = pipeline._with_flags(s_, fin)
    tr, va = s_["train"], s_["valid"]
    print(f"학습 {len(tr):,}(사건 {int(tr.y.sum())}) / 검증 {len(va):,}(사건 {int(va.y.sum())})\n")

    def ev(fit_df, label):
        m = model.ensemble().fit(fit_df[use], fit_df["y"])
        p = m.predict_proba(va[use])[:, 1]
        r = model.evaluate(va["y"], p, n_boot=300)
        print(f"  {label:<34} PR-AUC {r['PR-AUC']:.4f} {r['PR-AUC_95CI']}  "
              f"재현율@정밀도0.3 {r['재현율@정밀도0.3']:.3f}  n={len(fit_df):,}")
        return r

    print("=" * 72)
    print("[1] 매칭 학습 + 전수 평가 (docs/01 §4, Zmijewski 1984)")
    print("    업종·규모가 비슷한 정상 기업을 사건당 4개 매칭해 학습, 평가는 전수로")
    ev(tr, "전수 학습 (현행)")
    # 업종 2자리 × 로그자산 5분위로 층을 만들고 층 안에서 정상군 추출
    t = tr.copy()
    t["_ind"] = t["induty_code"].astype(str).str[:2] if "induty_code" in t else "00"
    t["_sz"] = pd.qcut(t["로그자산"], 5, labels=False, duplicates="drop")
    ev_rows = t[t.y == 1]
    picked = [ev_rows]
    for (i, z), g in ev_rows.groupby(["_ind", "_sz"], observed=True):
        pool = t[(t.y == 0) & (t._ind == i) & (t._sz == z)]
        k = min(len(pool), 4 * len(g))
        if k:
            picked.append(pool.sample(k, random_state=0))
    matched = pd.concat(picked).drop(columns=["_ind", "_sz"])
    print(f"    매칭 표본 사건비율 {matched.y.mean():.2%} (전수 {tr.y.mean():.2%})")
    ev(matched, "매칭 학습 → 전수 평가")

    print("\n" + "=" * 72)
    print("[2] 불균형 처리 3안")
    for label, est in [("class_weight=balanced (현행)", model.ensemble()),
                       ("가중 없음", model.ensemble(class_weight=None))]:
        m = est.fit(tr[use], tr["y"])
        p = m.predict_proba(va[use])[:, 1]
        r = model.evaluate(va["y"], p, n_boot=300)
        print(f"  {label:<34} PR-AUC {r['PR-AUC']:.4f} {r['PR-AUC_95CI']}")
    neg = tr[tr.y == 0].sample(min(len(tr[tr.y == 0]), 10 * int(tr.y.sum())), random_state=0)
    ev(pd.concat([tr[tr.y == 1], neg]), "언더샘플링 (정상:사건 = 10:1)")

    print("\n" + "=" * 72)
    print("[3] 그룹 분할 민감도 — 학습에 등장한 기업을 검증에서 빼면")
    seen = set(tr["corp_code"])
    va_new = va[~va["corp_code"].isin(seen)]
    m = model.ensemble().fit(tr[use], tr["y"])
    for label, d in [("검증 전체", va), ("학습에 없던 기업만", va_new)]:
        if len(d) < 50 or d.y.sum() < 5:
            print(f"  {label:<34} 표본 부족 (n={len(d)}, 사건={int(d.y.sum())})")
            continue
        p = m.predict_proba(d[use])[:, 1]
        r = model.evaluate(d["y"], p, n_boot=300)
        print(f"  {label:<34} PR-AUC {r['PR-AUC']:.4f} {r['PR-AUC_95CI']}  "
              f"n={len(d):,} 사건={int(d.y.sum())}")

    print("\n" + "=" * 72)
    print("[4] 인접 연도 중복 제거 — 기업별 격년만 사용")
    thin = tr[tr["bsns_year"] % 2 == 0]
    ev(thin, "학습을 격년으로 (관측치 절반)")


def shap():
    """9주차: SHAP 전역 기여도 · 안정성 필터 · 로지스틱 계수와의 정합성.

    **학습·검증 구간에서만** 계산한다. 평가 구간은 최종 1회만 연다.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from . import config, explain, model, pipeline
    plt.rcParams["font.family"] = ["AppleGothic", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    df = pipeline.load()
    s_, rep, fin, _ = pipeline._prepare(df)
    use = pipeline._with_flags(s_, fin)
    tr = s_["train"]
    out = config.RESULTS / "w09"; out.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("[1] 전역 기여도 (학습 구간, 평균 |SHAP|)")
    est = model.ensemble().fit(tr[use], tr["y"])
    sv = explain.shap_values(est, tr[use])
    glob = pd.Series(np.abs(sv).mean(0), index=use).sort_values(ascending=False)
    print(glob.head(12).round(4).to_string())
    glob.to_csv(out / "전역기여도.csv")

    print("\n" + "=" * 70)
    print("[2] 안정성 — 시드 5개로 재학습, 부호가 한 번도 안 뒤집힌 변수만 카드에 올린다")
    allow = explain.stable_features(
        lambda random_state: model.ensemble(random_state=random_state),
        tr[use], tr["y"], seeds=(0, 1, 2, 3, 4), top=99)
    dropped = [c for c in glob.index[:15] if c not in allow]
    print(f"  통과 {len(allow)}개 / 전체 {len(use)}개")
    print(f"  카드에 올릴 상위: {[c for c in glob.index if c in allow][:8]}")
    print(f"  기여도 상위 15 중 탈락: {dropped or '없음'}")
    pd.Series(allow).to_csv(out / "안정변수.csv", index=False, header=["변수"])

    print("\n" + "=" * 70)
    print("[3] 앙상블 SHAP 방향 vs 로지스틱 계수 부호")
    lr = model.baseline().fit(tr[use], tr["y"])
    lco = pd.Series(lr.named_steps["clf"].coef_[0], index=use)
    # SHAP 평균이 아니라 **값↔SHAP 상관**으로 비교한다. 평균은 0 근처 잡음이다
    sdir = explain.direction(tr[use], sv)
    cmp_ = pd.DataFrame({"SHAP방향": sdir, "로지스틱계수": lco, "기여도": glob})
    cmp_["부호일치"] = np.sign(cmp_.SHAP방향) == np.sign(cmp_.로지스틱계수)
    top = cmp_.sort_values("기여도", ascending=False).head(12)
    print(top.round(4).to_string())
    mism = top[~top.부호일치].index.tolist()
    print(f"\n  상위 12개 중 부호 불일치: {mism or '없음'}")
    cmp_.to_csv(out / "SHAP_계수_비교.csv")

    fig, ax = plt.subplots(figsize=(8, 6))
    g = glob.head(15)[::-1]
    ax.barh(range(len(g)), g.values, color=["#1F5F6B" if c in allow else "#C0C7CC" for c in g.index])
    ax.set_yticks(range(len(g))); ax.set_yticklabels(g.index, fontsize=9)
    ax.set_xlabel("평균 |SHAP|"); ax.set_title("전역 기여도 (회색 = 안정성 필터 탈락)")
    fig.tight_layout(); fig.savefig(out / "전역기여도.png", dpi=120); plt.close(fig)

    print("\n" + "=" * 70)
    print("[4] 설명 카드 예시 — 검증 구간 위험 상위 3건")
    res = {"splits": s_, "cols": use, "fits": {"앙상블": est}}
    cards, _ = pipeline.cards(res, n=3, part="valid")
    for c in cards:
        print(f"\n--- {c['corp_code']} FY{c['bsns_year']} (실제 사건 {c['y']})")
        print(c["card"])
    print(f"\n저장: {out}")


def faithful():
    """11주차: 설명 충실도 검증. **검증 구간에서만.**

    실무자에게 물을 수 없게 됐으므로 '납득되는가'는 확인 불가다.
    확인 가능한 것은 '설명이 모델을 정직하게 반영하는가'까지다.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from . import config, explain, model, pipeline
    plt.rcParams["font.family"] = ["AppleGothic", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    df = pipeline.load()
    s_, rep, fin, _ = pipeline._prepare(df)
    use = pipeline._with_flags(s_, fin)
    tr, va = s_["train"], s_["valid"]
    est = model.ensemble().fit(tr[use], tr["y"])
    out = config.RESULTS / "w11"; out.mkdir(parents=True, exist_ok=True)

    X = va[use].copy()
    base = est.predict_proba(X)[:, 1]
    med = tr[use].median()
    risky = np.argsort(-base)[:300]          # 위험 상위 300건에서 검사
    sv = explain.shap_values(est, X)

    print("=" * 70)
    print("[1] 삭제 검사 — SHAP 상위 k개를 중앙값으로 치환하면 확률이 떨어지는가")
    print("    떨어지지 않으면 그 설명은 모델의 근거가 아니다\n")
    rng = np.random.default_rng(0)
    ks = [1, 2, 3, 5, 8, 12]
    curve = {"k": ks, "SHAP상위": [], "무작위": []}
    for k in ks:
        for mode in ("shap", "rand"):
            Z = X.copy()
            for i in risky:
                if mode == "shap":
                    cols = np.argsort(-sv[i])[:k]        # 위험을 올린 상위 k
                else:
                    cols = rng.choice(len(use), k, replace=False)
                for j in cols:
                    Z.iloc[i, j] = med.iloc[j]
            p = est.predict_proba(Z)[:, 1][risky]
            drop = float((base[risky] - p).mean())
            curve["SHAP상위" if mode == "shap" else "무작위"].append(drop)
    t = pd.DataFrame(curve).set_index("k")
    t["차이"] = t["SHAP상위"] - t["무작위"]
    print(t.round(4).to_string())
    t.to_csv(out / "삭제검사.csv")
    ok = (t["차이"] > 0).all()
    print(f"\n  모든 k 에서 SHAP 상위가 무작위보다 크게 떨어뜨림: {'예' if ok else '아니오'}")
    print(f"  k=3 기준 SHAP {t.loc[3,'SHAP상위']:.4f} vs 무작위 {t.loc[3,'무작위']:.4f} "
          f"({t.loc[3,'SHAP상위']/max(t.loc[3,'무작위'],1e-9):.1f}배)")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(t.index, t["SHAP상위"], marker="o", label="SHAP 상위 k개 치환", color="#1F5F6B")
    ax.plot(t.index, t["무작위"], marker="s", ls="--", label="무작위 k개 치환", color="#A9702A")
    ax.set_xlabel("치환한 변수 개수 k"); ax.set_ylabel("부실확률 평균 하락폭")
    ax.set_title("삭제 검사 (검증 구간 위험 상위 300건)"); ax.legend()
    fig.tight_layout(); fig.savefig(out / "삭제검사.png", dpi=120); plt.close(fig)

    print("\n" + "=" * 70)
    print("[2] 카드 문장이 관측값과 모순되는 사례")
    allow = explain.stable_features(
        lambda random_state: model.ensemble(random_state=random_state), tr[use], tr["y"], top=99)
    ref = tr[use].median()
    n_card = n_bad = 0
    bad_by_var = {}
    for i in risky[:150]:
        row, contrib = X.iloc[i], pd.Series(sv[i], index=use)
        for name, c in contrib.items():
            if name not in allow or name.endswith("_결측"):
                continue
            side = explain._risky_side(name, row.get(name), ref)
            if side is None:
                continue
            n_card += 1
            if (c > 0) != side:                 # 묶음과 문장이 반대 방향
                n_bad += 1
                bad_by_var[name] = bad_by_var.get(name, 0) + 1
    print(f"  검사한 (사례 × 변수) {n_card:,}건 중 모순 {n_bad:,}건 ({n_bad/max(n_card,1):.1%})")
    print("  변수별 모순 빈도:")
    for k_, v_ in sorted(bad_by_var.items(), key=lambda x: -x[1])[:8]:
        print(f"    {k_:<16} {v_}")
    print("\n  → 모순은 버그가 아니라 모델이 관측값과 반대로 판단한 지점이다. 12주차 재료.")
    print(f"\n저장: {out}")


def w12():
    """12주차: 오분류 사례 분석. 미탐 8 · 오탐 8 · 정탐 4 (검증 구간).

    감사인이 남긴 텍스트(강조사항·핵심감사사항)를 함께 붙여 본다 —
    모델이 못 본 것이 재무제표 밖에 있었는지 확인하려는 것이다.
    """
    import numpy as np
    import pandas as pd
    from . import config, dart, explain, labels, model, pipeline
    df = pipeline.load()
    s_, rep, fin, _ = pipeline._prepare(df)
    use = pipeline._with_flags(s_, fin)
    tr, va = s_["train"], s_["valid"]
    est = model.ensemble().fit(tr[use], tr["y"])
    cal = model.calibrated(model.ensemble, "isotonic").fit(tr[use], tr["y"])
    out = config.RESULTS / "w12"; out.mkdir(parents=True, exist_ok=True)

    va = va.copy()
    va["p"] = cal.predict_proba(va[use])[:, 1]
    va["순위"] = va["p"].rank(ascending=False, method="first").astype(int)
    hi = va["p"].quantile(0.95)                       # 상위 5% 를 '고위험'으로 본다
    miss = va[(va.y == 1) & (va.p < hi)].nsmallest(8, "p")     # 미탐
    fp = va[(va.y == 0) & (va.p >= hi)].nlargest(8, "p")       # 오탐
    tp = va[(va.y == 1) & (va.p >= hi)].nlargest(4, "p")       # 정탐

    print(f"검증 구간 {len(va):,}건 / 사건 {int(va.y.sum())}건 / 고위험 임계 {hi:.3f}")
    print(f"미탐 {len(miss)} · 오탐 {len(fp)} · 정탐 {len(tp)}\n")

    names = {r["corp_code"]: r["corp_name"] for r in dart.corp_codes()}
    rows = []
    for label, part in [("미탐", miss), ("오탐", fp), ("정탐", tp)]:
        for _, r in part.iterrows():
            cc, y = r["corp_code"], int(r["bsns_year"])
            ao = labels.current_period(dart.audit_opinion(cc, y)) or {}
            emph = (ao.get("emphs_matter") or "").replace("\n", " ").strip()
            gc = any(k in emph for k in labels.GOING_CONCERN)
            rows.append({
                "유형": label, "기업": names.get(cc, cc)[:14], "FY": y,
                "확률": round(float(r["p"]), 4), "실제": int(r["y"]),
                "감사의견": labels.classify_opinion(ao.get("adt_opinion")),
                "계속기업언급": "○" if gc else "",
                "강조사항": (emph[:60] + "…") if len(emph) > 60 else emph,
            })
    t = pd.DataFrame(rows)
    print(t.drop(columns=["강조사항"]).to_string(index=False))
    t.to_csv(out / "오분류_사례.csv", index=False)

    print("\n" + "=" * 70)
    print("[진단] 미탐 기업의 직전 보고서에 이미 신호가 있었는가")
    for label in ("미탐", "오탐", "정탐"):
        g = t[t.유형 == label]
        print(f"  {label}: 계속기업 불확실성 언급 {int((g.계속기업언급=='○').sum())}/{len(g)}"
              f" · 감사의견 비적정 {int((g.감사의견=='비적정').sum())}/{len(g)}")

    print("\n" + "=" * 70)
    print("[미탐 사례 상세] 모델이 본 것 vs 감사인이 적은 것")
    sv = explain.shap_values(est, va[use])
    allow = explain.stable_features(
        lambda random_state: model.ensemble(random_state=random_state), tr[use], tr["y"], top=99)
    ref = tr[use].median()
    idx = {v: i for i, v in enumerate(va.index)}
    for _, r in miss.head(4).iterrows():
        i = idx[r.name]
        print(f"\n--- {names.get(r['corp_code'], r['corp_code'])[:14]} FY{int(r['bsns_year'])}"
              f"  확률 {r['p']:.1%} (실제 사건)")
        print(explain.card(va[use].iloc[i], sv[i], use, allow=allow, ref=ref, top_k=3))
        row = t[(t.기업 == names.get(r["corp_code"], r["corp_code"])[:14]) & (t.FY == int(r["bsns_year"]))]
        if len(row):
            e = row.iloc[0]["강조사항"]
            print(f"  감사인 강조사항: {e or '(없음)'}")
    print(f"\n저장: {out}")


def w13():
    """13주차: 재무제표에 담기지 않는 정보 — 전수 측정 + 변수 추가 실험.

    12주차는 군당 8건이라 아무것도 확정할 수 없었다. 여기서 전수로 다시 잰다.
    사건군에서 많이 나오는 것만으로는 신호가 아니다. **정상군 대비**를 함께 본다.
    """
    import numpy as np
    import pandas as pd
    from . import config, dart, labels, model, pipeline
    df = pipeline.load()
    out = config.RESULTS / "w13"; out.mkdir(parents=True, exist_ok=True)

    print("=" * 74)
    print("[1] 감사인 텍스트·공시 행태 신호를 전수로 적재")
    rows = []
    prev_auditor = {}
    for cc, g in df.sort_values(["corp_code", "bsns_year"]).groupby("corp_code"):
        for _, r in g.iterrows():
            y = int(r["bsns_year"])
            ao = labels.current_period(dart.audit_opinion(cc, y)) or {}
            emph = (ao.get("emphs_matter") or "").replace("\n", " ")
            spc = (ao.get("adt_reprt_spcmnt_matter") or "").replace("\n", " ")
            core = (ao.get("core_adt_matter") or "").replace("\n", " ")
            blob = f"{emph} {spc}"
            aud = (ao.get("adtor") or "").strip()
            chg = int(bool(aud) and cc in prev_auditor and prev_auditor[cc] != aud)
            if aud:
                prev_auditor[cc] = aud
            rows.append({
                "corp_code": cc, "bsns_year": y,
                "계속기업불확실성": float(any(k in blob for k in labels.GOING_CONCERN)),
                "강조사항있음": float(emph.strip() not in ("", "-", "해당사항 없음", "해당사항없음")),
                "핵심감사사항수": float(core.count("\n") + (1 if core.strip() else 0)),
                "감사인교체": float(chg),
            })
    sig = pd.DataFrame(rows)
    d = df.merge(sig, on=["corp_code", "bsns_year"], how="left")
    if "제출기한연장" in d.columns:
        pass
    else:
        d["제출기한연장"] = 0.0
    cols = ["계속기업불확실성", "강조사항있음", "감사인교체", "제출기한연장"]
    d[cols] = d[cols].fillna(0.0)

    print("\n[2] 사건군 vs 정상군 등장 비율 — **정상군 대비를 함께 본다**")
    tab = []
    for c in cols:
        a_, b_ = d.loc[d.y == 1, c].mean(), d.loc[d.y == 0, c].mean()
        # 사건 예측력: 그 신호가 있을 때의 사건비율 / 없을 때의 사건비율
        on = d.loc[d[c] == 1, "y"].mean() if (d[c] == 1).any() else np.nan
        off = d.loc[d[c] == 0, "y"].mean()
        tab.append({"신호": c, "사건군": a_, "정상군": b_, "차이": a_ - b_,
                    "신호있을때 사건비율": on, "없을때": off,
                    "배수": on / off if off else np.nan})
    t = pd.DataFrame(tab).set_index("신호")
    print(t.round(4).to_string())
    t.to_csv(out / "담기지않는정보_전수.csv")

    print("\n" + "=" * 74)
    print("[3] 변수 추가 실험 — 검증 구간. 시점 정합: FY t-1 값만 쓴다")
    d = d.sort_values(["corp_code", "bsns_year"])
    for c in cols:
        d[f"전기_{c}"] = d.groupby("corp_code")[c].shift(1)
    lag = [f"전기_{c}" for c in cols]
    s_, rep, fin, _ = pipeline._prepare(d)
    base_cols = pipeline._with_flags(s_, fin)
    for name, extra in [("재무 27개 (현행)", []),
                        ("+ 계속기업불확실성", ["전기_계속기업불확실성"]),
                        ("+ 공시행태 4종", lag)]:
        use = base_cols + [c for c in extra if c in s_["train"].columns]
        m = model.ensemble().fit(s_["train"][use].fillna(0), s_["train"]["y"])
        p = m.predict_proba(s_["valid"][use].fillna(0))[:, 1]
        r = model.evaluate(s_["valid"]["y"], p, n_boot=300)
        print(f"  {name:<22} PR-AUC {r['PR-AUC']:.4f} {r['PR-AUC_95CI']}  "
              f"재현율@정밀도0.3 {r['재현율@정밀도0.3']:.3f}")
    d.to_csv(config.PROCESSED / "dataset_signals.csv", index=False)
    print(f"\n저장: {out} · data/processed/dataset_signals.csv")


def explain_cards():
    from . import pipeline
    res = pipeline.train()
    out, allow = pipeline.cards(res)
    print(f"안정 변수 {len(allow)}개: {allow}\n")
    for c in out:
        print(f"--- {c['corp_code']} FY{c['bsns_year']} (실제 {c['y']})\n{c['card']}\n")


STEPS = {"corp": corp, "probe": probe, "fs": fs, "dryrun": dryrun, "build": build, "tables": tables, "eda": eda, "train": train,
         "diagnose": diagnose, "calibrate": calibrate, "prices": prices, "compare": compare, "w08": w08, "shap": shap, "faithful": faithful, "w12": w12, "w13": w13, "explain": explain_cards}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in STEPS:
        print("사용법: python -m hup.cli " + "|".join(STEPS))
        sys.exit(1)
    STEPS[sys.argv[1]]()
