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
    import pandas as pd
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
    from . import config, dataset, model, pipeline, features
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
    import numpy as np
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
    from . import config, dataset, features, model, pipeline
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
    import pandas as pd
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
    import numpy as np
    import pandas as pd
    from . import config, dataset, model, pipeline
    rng = np.random.default_rng(0)
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
    for label, d in [("검증 전체", va), (f"학습에 없던 기업만", va_new)]:
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


def explain_cards():
    from . import pipeline
    res = pipeline.train()
    out, allow = pipeline.cards(res)
    print(f"안정 변수 {len(allow)}개: {allow}\n")
    for c in out:
        print(f"--- {c['corp_code']} FY{c['bsns_year']} (실제 {c['y']})\n{c['card']}\n")


def compare():
    from . import pipeline
    r = pipeline.compare()
    print(f"기준선(사건비율) PR-AUC = {r['기준선']:.4f}\n")
    for name, sc in r["결과"].items():
        for k, v in sc.items():
            print(f"{name:8s} {k:12s} PR-AUC {v['PR-AUC']:.4f} {v['PR-AUC_95CI']} "
                  f"| 기준선 대비 {v['PR-AUC']/r['기준선']:.1f}배")


STEPS = {"corp": corp, "probe": probe, "fs": fs, "dryrun": dryrun, "build": build, "tables": tables, "eda": eda, "train": train,
         "diagnose": diagnose, "calibrate": calibrate, "prices": prices, "compare": compare, "w08": w08, "explain": explain_cards, "compare": compare}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in STEPS:
        print("사용법: python -m hup.cli " + "|".join(STEPS))
        sys.exit(1)
    STEPS[sys.argv[1]]()
