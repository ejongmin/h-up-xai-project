# 2차 실험 — docs/15 §5·§6 그대로 실행한다.
#   HUP_VERSION=v2 PYTHONPATH=src .venv/bin/python scripts/v2_experiment.py select     검증 구간만 본다
#   (선택 결과 커밋)
#   HUP_VERSION=v2 PYTHONPATH=src .venv/bin/python scripts/v2_experiment.py evaluate   평가 구간을 한 번 연다
import hashlib
import json
import platform
import subprocess
import sys
import time
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score

from hup import config, dataset, explain, features, model, pipeline

assert config.VERSION.startswith("v2"), "HUP_VERSION=v2.1 로 실행할 것"
OUT = config.RESULTS / "selection"
FINAL = config.RESULTS / "final"
MODEL_FILE = config.PROCESSED / "v2_final_model.joblib"
ORDER = ["로지스틱", "HistGB", "랜덤포레스트"]


def git(*a):
    return subprocess.run(["git", *a], cwd=config.ROOT, capture_output=True, text=True).stdout.strip()


def sha(path, n=16):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def env():
    return {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__,
            "pandas": pd.__version__, "os": platform.platform()}


def frames():
    """docs/15 §5-2 공통 조건 — 검토 대상·주 분석 제외 행을 뺀 v2 데이터, 엠바고 분할, 학습 구간 기준 정제."""
    df = pipeline.load()
    df = df[df["검토필요"] == 0]
    s = dataset.split(df, horizon_days=config.HORIZON_DAYS)
    dataset.sanity(s, config.HORIZON_DAYS)
    fin = [c for c in features.FEATURE_COLS if c in df.columns]
    st = dataset.fit_clean(s["train"], cols=fin)
    s = {k: dataset.apply_clean(v, st) for k, v in s.items()}
    use = pipeline._with_flags(s, fin)
    return df, s, use


def select():
    if git("status", "--porcelain", "--", "src", "scripts", "docs", "tests"):
        sys.exit("작업 트리가 깨끗하지 않다 — 커밋한 뒤 실행할 것 (실행 기록의 커밋이 코드를 재현해야 한다)")
    df, s, use = frames()
    tr, va = s["train"], s["valid"]
    first = (va["과거사건"] == 0).to_numpy()
    yv, gv = va["y"].to_numpy()[first], va["corp_code"].to_numpy()[first]
    rows, preds = [], {}
    for name in ORDER:
        for i, cfg in enumerate(model.GRIDS[name]):
            t0 = time.time()
            rec = {"모델": name, "번호": i, "설정": json.dumps(cfg, ensure_ascii=False)}
            try:
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    m = model.candidate(name, **cfg).fit(tr[use], tr["y"])
                    p = m.predict_proba(va[use])[:, 1]
                ap = float(average_precision_score(yv, p[first]))
                rec.update(상태="성공", 경고=len(w), 경고_예=str(w[0].message)[:120] if w else "",
                           검증_첫부실_PR_AUC=round(ap, 5), 검증_첫부실_PR_AUC_원값=ap,
                           검증_전체_PR_AUC=round(float(average_precision_score(va["y"], p)), 5))
                preds[(name, i)] = (m, p)
            except Exception as e:                      # 실패도 그대로 남긴다 — 다른 설정으로 바꾸지 않는다 (§5-3)
                rec.update(상태="실패", 오류=f"{type(e).__name__}: {e}"[:300])
            rec["초"] = round(time.time() - t0, 1)
            rows.append(rec)
            print(rec, flush=True)
    t = pd.DataFrame(rows)
    ok = t[t["상태"] == "성공"]
    best = {}
    for name in ORDER:
        g = ok[ok["모델"] == name]
        if len(g):     # 같은 점수면 목록 앞 설정 (§5-3)
            # 같은 점수 판정은 원래 정밀도로 (v2.1 — 반올림 동점으로 HistGB 최고 설정이 바뀌었다)
            r = g.sort_values(["검증_첫부실_PR_AUC_원값", "번호"], ascending=[False, True]).iloc[0]
            best[name] = int(r["번호"])
    if "로지스틱" not in best:
        sys.exit("기준 모델(로지스틱)이 20개 설정 모두 실패했다 — 결과표를 보고 원인을 기록할 것. 다른 설정으로 바꾸지 않는다")
    top = max(ORDER, key=lambda n: (n in best, average_precision_score(yv, preds[(n, best[n])][1][first]) if n in best else -1))
    pl = preds[("로지스틱", best["로지스틱"])][1][first]
    comp = {}
    for name in best:
        if name != "로지스틱":
            d, ci = model.paired_ap_diff(yv, preds[(name, best[name])][1][first], pl, gv, n_boot=1000, seed=0)
            comp[name] = {"차이(모델−로지스틱)": round(d, 5), "95%구간": [round(ci[0], 5), round(ci[1], 5)]}
    if top == "로지스틱":
        chosen, why = "로지스틱", "검증 첫 부실 PR-AUC 최고가 로지스틱"
    elif comp[top]["95%구간"][0] > 0:
        chosen, why = top, f"{top} 가 최고이고 로지스틱과의 차이 구간이 0 을 포함하지 않는다"
    else:
        chosen, why = "로지스틱", (f"{top} 가 최고지만 로지스틱과의 차이 구간이 0 을 포함 — 운영 규칙상 단순한 모델. "
                                    "성능이 같다는 뜻이 아니라 차이를 확인할 증거가 부족하다는 뜻 (§5-2)")
    m, p = preds[(chosen, best[chosen])]
    thr = model.threshold_at_precision(yv, p[first], 0.30)
    cfg = model.GRIDS[chosen][best[chosen]]
    cal = model.calibrated(lambda: model.candidate(chosen, **cfg), "isotonic").fit(tr[use], tr["y"])
    joblib.dump({"model": m, "calibrated": cal, "use": use, "chosen": chosen, "config": cfg}, MODEL_FILE)

    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "설정별_검증성능.csv", index=False, encoding="utf-8-sig")
    flagged = p[first] >= thr if thr is not None else np.zeros(first.sum(), bool)
    rec = {
        "단계": "선택 (검증 구간만 사용)", "실행": time.strftime("%Y-%m-%d %H:%M:%S"),
        "커밋": git("rev-parse", "--short", "HEAD"), "데이터": json.loads((config.PROCESSED / "MANIFEST.json").read_text()),
        "환경": env(), "시드": {"모델": 42, "부트스트랩": 0, "HistGB 설정 추출": 0},
        "학습": {"n": len(tr), "사건": int(tr["y"].sum())},
        "검증_첫부실": {"n": int(first.sum()), "사건": int(yv.sum()), "기준선": round(float(yv.mean()), 5)},
        "변수": use, "설정 수": {n: len(model.GRIDS[n]) for n in ORDER},
        "실패": int((t["상태"] == "실패").sum()),
        "모델별 최고": {n: {"번호": best[n], "설정": model.GRIDS[n][best[n]],
                          "검증_첫부실_PR_AUC": float(t[(t["모델"] == n) & (t["번호"] == best[n])]["검증_첫부실_PR_AUC"].iloc[0])}
                     for n in best},
        "로지스틱 대비 차이 (쌍 부트스트랩, 기업 군집 1,000회)": comp,
        "최종 모델": chosen, "선택 사유": why, "최종 설정": cfg,
        "경보 임계값 (검증 첫 부실, 정밀도 30% 이상인 가장 낮은 점수)": thr,
        "검증에서 임계값의 경보 수": int(flagged.sum()),
        "주의": "검증 점수는 20개 중 최고를 고른 값이라 낙관적이다 — 선택에만 쓰고 성능으로 보고하지 않는다",
        "모델 파일 sha256(16)": sha(MODEL_FILE),
    }
    (OUT / "선택결과.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2, default=float))
    # §5-2 1: 고른 로지스틱의 계수 부호를 재무 상식과 대조
    lg = preds[("로지스틱", best["로지스틱"])][0].named_steps["clf"]
    coef = pd.DataFrame({"변수": use, "계수": lg.coef_[0]})
    base = coef["변수"].str.replace("_결측", "", regex=False)
    coef["기대 방향"] = np.where(coef["변수"].str.endswith("_결측"), "",
                             np.where(base.isin(explain.HIGH_IS_RISKY), "+", "−"))
    coef["일치"] = np.where(coef["기대 방향"] == "", "", np.where(
        (coef["계수"] == 0), "0 (L1 제거)", np.where((coef["계수"] > 0) == (coef["기대 방향"] == "+"), "일치", "불일치")))
    coef.to_csv(OUT / "로지스틱_계수부호.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({k: rec[k] for k in ("모델별 최고", "로지스틱 대비 차이 (쌍 부트스트랩, 기업 군집 1,000회)",
                                          "최종 모델", "선택 사유", "경보 임계값 (검증 첫 부실, 정밀도 30% 이상인 가장 낮은 점수)", "실패")},
                     ensure_ascii=False, indent=1, default=float))


def evaluate():
    sel = OUT / "선택결과.json"
    if not sel.exists() or git("status", "--porcelain", "--", str(OUT)) or not git("ls-files", str(sel)):
        sys.exit("선택 결과가 커밋돼 있지 않다 — select 결과를 커밋한 뒤 평가할 것 (§5-3)")
    out = FINAL / "평가결과.json"
    if out.exists():
        sys.exit("평가 결과가 이미 있다 — 평가 구간은 한 번만 연다 (§6)")
    rec = json.loads(sel.read_text())
    if sha(MODEL_FILE) != rec["모델 파일 sha256(16)"]:
        sys.exit("모델 파일이 선택 때와 다르다")
    b = joblib.load(MODEL_FILE)
    df, s, use = frames()
    assert use == b["use"], "변수 목록이 선택 때와 다르다"
    te = s["test"]
    p = b["model"].predict_proba(te[use])[:, 1]
    pc = b["calibrated"].predict_proba(te[use])[:, 1]
    thr = rec["경보 임계값 (검증 첫 부실, 정밀도 30% 이상인 가장 낮은 점수)"]

    def block(mask, name):
        y, g = te["y"].to_numpy()[mask], te["corp_code"].to_numpy()[mask]
        r = model.evaluate(y, p[mask], groups=g)
        r = {k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()}
        r["재현율@정밀도0.3 (참고 — 평가 구간에서 고른 경계)"] = r.pop("재현율@정밀도0.3")
        r.pop("Brier", None)
        r["Brier (보정 확률)"] = float(np.mean((pc[mask] - y) ** 2))
        r["기준선"] = float(y.mean())
        if thr is not None:
            f = p[mask] >= thr
            tp = int((f & (y == 1)).sum())
            r["경보 (검증에서 정한 임계값 그대로)"] = {"경보 수": int(f.sum()), "적중": tp,
                                              "정밀도": tp / f.sum() if f.sum() else None, "재현율": tp / y.sum() if y.sum() else None}
        return {name: r}

    first = (te["과거사건"] == 0).to_numpy()
    res = {}
    res.update(block(first, "관측 기간 내 첫 부실 (주 분석)"))
    res.update(block(np.ones(len(te), bool), "전체 (보조)"))
    res.update(block(~first, "반복 부실 (보조)"))
    sens = {}
    for h in config.HORIZON_SENSITIVITY:     # 보조 분석: 같은 예측, 라벨만 다른 창
        if h == config.HORIZON_DAYS:
            continue
        lab = pd.read_csv(config.PROCESSED / f"dataset_h{h}.csv", dtype={"corp_code": str}, usecols=["corp_code", "bsns_year", "y"])
        yh = te[["corp_code", "bsns_year"]].merge(lab, on=["corp_code", "bsns_year"], how="left")["y"].fillna(0).to_numpy()
        sens[f"{h}일"] = {"첫 부실 PR-AUC": float(average_precision_score(yh[first], p[first])), "첫 부실 사건": int(yh[first].sum())}
    FINAL.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"성격": "2차 수정 후 재평가 (평가 구간 2024~2025, 독립 검증 아님 — docs/15 §6)",
                               "실행": time.strftime("%Y-%m-%d %H:%M:%S"), "커밋": git("rev-parse", "--short", "HEAD"),
                               "선택 커밋": rec["커밋"], "최종 모델": rec["최종 모델"], "최종 설정": rec["최종 설정"],
                               "경보 임계값": thr, "환경": env(), "결과": res, "예측 창 민감도 (보조)": sens},
                              ensure_ascii=False, indent=2, default=float))
    print(out.read_text())


if __name__ == "__main__":
    {"select": select, "evaluate": evaluate}[sys.argv[1]]()
