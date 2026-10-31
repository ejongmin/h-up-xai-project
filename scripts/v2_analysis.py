# 11~13주차 분석을 2차 동결 모델 · 검증 구간으로 다시 (docs/15 §9 — 실행 전 고정)
# 실행: HUP_VERSION=v2 PYTHONPATH=src .venv/bin/python scripts/v2_analysis.py → results/v2/analysis/
import importlib.util
import json
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from hup import config, dart, explain, labels, model

spec = importlib.util.spec_from_file_location("exp", config.ROOT / "scripts" / "v2_experiment.py")
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)
if exp.git("status", "--porcelain", "--", "src", "scripts", "docs"):
    sys.exit("작업 트리가 깨끗하지 않다 — 커밋한 뒤 실행할 것")

OUT = config.RESULTS / "analysis"
OUT.mkdir(parents=True, exist_ok=True)
b = joblib.load(config.RESULTS / "freeze" / "모델.joblib")
est, cfg = b["model"], b["config"]
df, s, use = exp.frames()
assert use == b["use"]
raw = df                                   # 정제 전 원본 값 (검토필요=0)
tr, va = s["train"], s["valid"]
ref = tr[use].median()
score = pd.Series(est.predict_proba(va[use])[:, 1], index=va.index)
first = va["과거사건"] == 0
rec = {"커밋": exp.git("rev-parse", "--short", "HEAD"), "모델": "동결 랜덤포레스트 (results/v2/freeze/모델.joblib)", "구간": "검증 T 2022~2023"}

# ---- W11-1 삭제 검사
print("[W11-1] 삭제 검사", flush=True)
rows = []
for name, mask in (("검증 첫 부실 (주)", first), ("검증 전체 (보조)", pd.Series(True, index=va.index))):
    X = va.loc[mask, use]
    p0 = est.predict_proba(X)[:, 1]
    top = np.argsort(-p0)[:300]
    sv = explain.shap_values(est, X.iloc[top])
    rng = np.random.default_rng(0)
    for k in (1, 2, 3, 5, 8, 12):
        drop = {}
        for mode in ("SHAP상위", "무작위"):
            Z = X.iloc[top].copy()
            for j in range(len(top)):
                cols = np.argsort(-sv[j])[:k] if mode == "SHAP상위" else rng.choice(len(use), k, replace=False)
                for c in cols:
                    Z.iat[j, c] = ref[use[c]]
            drop[mode] = float(np.mean(p0[top] - est.predict_proba(Z)[:, 1]))
        rows.append({"대상": name, "k": k, "SHAP상위 하락": round(drop["SHAP상위"], 4), "무작위 하락": round(drop["무작위"], 4),
                     "배수": round(drop["SHAP상위"] / drop["무작위"], 1) if drop["무작위"] > 0 else None})
w111 = pd.DataFrame(rows)
w111.to_csv(OUT / "W11_삭제검사.csv", index=False, encoding="utf-8-sig")
print(w111.to_string(index=False), flush=True)

# ---- W11-2 사실 단정 · 보류
print("[W11-2] 사실 단정 · 보류 (안정 변수 계산 중)", flush=True)
allow = explain.stable_features(lambda random_state: model.candidate("랜덤포레스트", random_state=random_state, **cfg),
                                tr[use], tr["y"], top=len(use))
rows, reasons = [], []
for name, mask in (("첫 부실", first), ("부실 이력 있음", ~first)):
    sc = score[mask].sort_values(ascending=False)
    top = sc.index[: int(len(sc) * 0.10)]
    sv = pd.DataFrame(explain.shap_values(est, va.loc[top, use]), index=top, columns=use)
    n_line = n_over = n_hold = 0
    for ix in top:
        row, v = raw.loc[ix], sv.loc[ix]
        why = explain.hold_reasons(row, v.to_numpy(), use, allow, ref)
        if why:
            n_hold += 1
            reasons += [(name, w.split(" — ")[0]) for w in why]
            continue
        sh = explain._shown(v, allow, explain._equity_wiped(row))
        lines = list(sh[sh > 0].sort_values(ascending=False).head(4).index) + list(sh[sh < -1e-3].sort_values().head(2).index)
        n_line += len(lines)
        n_over += sum(bool(explain._risky_side(n, row.get(n), ref)) and explain.overstated(n, row.get(n)) for n in lines)
    rows.append({"집단": name, "카드": len(top), "보류": n_hold, "보류율": round(n_hold / len(top), 4), "카드 줄": n_line,
                 "구 방식이면 사실과 다른 단정": n_over, "비율": round(n_over / max(n_line, 1), 4), "현행 카드의 사실 단정 오류": 0})
w112 = pd.DataFrame(rows)
w112.to_csv(OUT / "W11_사실단정_보류.csv", index=False, encoding="utf-8-sig")
pd.Series(reasons, dtype=object).value_counts().rename_axis("집단·사유").reset_index(name="건수").to_csv(
    OUT / "W11_보류사유.csv", index=False, encoding="utf-8-sig")
print(w112.to_string(index=False), "\n안정 변수", len(allow), flush=True)

# ---- W12 오분류
print("[W12] 오분류", flush=True)
cols = ["ROA", "이자보상배율", "부채비율", "유동비율", "자본잠식률", "영업현금흐름_매출"]
tabs, counts = [], []
for name, mask in (("검증 첫 부실 (주)", first), ("검증 전체 (보조)", pd.Series(True, index=va.index))):
    sc, y = score[mask], va.loc[mask, "y"]
    hi = sc.quantile(0.95)
    g = pd.Series("정상", index=sc.index)
    g[(y == 1) & (sc < hi)] = "미탐"
    g[(y == 1) & (sc >= hi)] = "정탐"
    g[(y == 0) & (sc >= hi)] = "오탐"
    t = raw.loc[sc.index, cols].groupby(g).median().T.reindex(columns=["미탐", "정탐", "오탐", "정상"])
    t.columns = [f"{name}_{c}" for c in t.columns]
    tabs.append(t)
    counts.append({"대상": name, "고위험 기준(상위 5%) 점수": round(float(hi), 4), **g.value_counts().to_dict()})
w12 = pd.concat(tabs, axis=1).round(4)
w12.to_csv(OUT / "W12_오분류_재무중앙값.csv", encoding="utf-8-sig")
pd.DataFrame(counts).to_csv(OUT / "W12_오분류_수.csv", index=False, encoding="utf-8-sig")
print(pd.DataFrame(counts).to_string(index=False)); print(w12.to_string(), flush=True)

# ---- W13 추가 공시정보
print("[W13] 추가 공시정보", flush=True)
sig = []
prev_aud = {}
keys = sorted(set(zip(df["corp_code"], df["bsns_year"])))
for cc, y in keys:
    ao = labels.current_period(dart.audit_opinion(cc, int(y))) or {}
    emph = (ao.get("emphs_matter") or "").replace("\n", " ")
    blob = f"{emph} {(ao.get('adt_reprt_spcmnt_matter') or '')}"
    aud = (ao.get("adtor") or "").strip()
    chg = float(bool(aud) and cc in prev_aud and prev_aud[cc] != aud)
    if aud:
        prev_aud[cc] = aud
    sig.append({"corp_code": cc, "bsns_year": int(y), "계속기업불확실성": float(any(k in blob for k in labels.GOING_CONCERN)),
                "강조사항있음": float(emph.strip() not in ("", "-", "해당사항 없음", "해당사항없음")), "감사인교체": chg})
sig = pd.DataFrame(sig).sort_values(["corp_code", "bsns_year"])
lagcols = []
for c in ("계속기업불확실성", "강조사항있음", "감사인교체"):
    sig[f"전기_{c}"] = sig.groupby("corp_code")[c].shift(1)
    lagcols.append(f"전기_{c}")
sigtab = []
d = df.merge(sig, on=["corp_code", "bsns_year"], how="left")
for c in ("계속기업불확실성", "강조사항있음", "감사인교체", "제출기한연장"):
    on, off = d.loc[d[c] == 1, "y"].mean(), d.loc[d[c] == 0, "y"].mean()
    sigtab.append({"신호": c, "사건군 비율": round(d.loc[d.y == 1, c].mean(), 4), "정상군 비율": round(d.loc[d.y == 0, c].mean(), 4),
                   "신호 있을 때 사건비율": round(on, 4), "없을 때": round(off, 4), "배수": round(on / off, 1) if off else None})
pd.DataFrame(sigtab).to_csv(OUT / "W13_신호_전수.csv", index=False, encoding="utf-8-sig")
add = lagcols + ["제출기한연장"]


def with_sig(frame):
    m = frame.merge(sig[["corp_code", "bsns_year"] + lagcols], on=["corp_code", "bsns_year"], how="left")
    m.index = frame.index
    return m[use + add].fillna({c: 0.0 for c in add})


Xtr, Xva = with_sig(tr), with_sig(va)
base_re = model.candidate("랜덤포레스트", n_jobs=1, **cfg).fit(tr[use], tr["y"])
p_base = est.predict_proba(va[use])[:, 1]
assert np.allclose(base_re.predict_proba(va[use])[:, 1], p_base), "동결 설정 재학습이 동결 모델과 다르다"
m_sig = model.candidate("랜덤포레스트", n_jobs=1, **cfg).fit(Xtr, tr["y"])
p_sig = m_sig.predict_proba(Xva)[:, 1]
fm = first.to_numpy()
yv, gv = va["y"].to_numpy(), va["corp_code"].to_numpy()
w13 = []
for name, mk in (("검증 첫 부실 (주)", fm), ("검증 전체 (보조)", np.ones(len(va), bool))):
    dlt, ci = model.paired_ap_diff(yv[mk], p_sig[mk], p_base[mk], gv[mk], n_boot=1000, seed=0)
    w13.append({"대상": name, "동결 모델 PR-AUC": round(average_precision_score(yv[mk], p_base[mk]), 4),
                "+신호 4종 PR-AUC": round(average_precision_score(yv[mk], p_sig[mk]), 4),
                "차이": round(dlt, 4), "95% 구간": [round(ci[0], 4), round(ci[1], 4)],
                "판정": "추가 이득을 확인하지 못함 (구간이 0 포함 — 같다는 뜻 아님)" if ci[0] <= 0 <= ci[1] else
                        ("구간이 0 보다 큼 — 동결 모델은 바꾸지 않음, 향후 과제" if ci[0] > 0 else "구간이 0 보다 작음 — 더하면 나빠짐")})
pd.DataFrame(w13).to_csv(OUT / "W13_신호추가.csv", index=False, encoding="utf-8-sig")
print(pd.DataFrame(sigtab).to_string(index=False)); print(pd.DataFrame(w13).to_string(index=False))
rec.update(W11_삭제검사=w111.to_dict("records"), W11_사실단정_보류=w112.to_dict("records"), W12_수=counts, W13=w13)
(OUT / "요약.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=float))
