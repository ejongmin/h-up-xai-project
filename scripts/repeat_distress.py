# 실행: PYTHONPATH=src .venv/bin/python scripts/repeat_distress.py  (docs/10 §3-18)
# 첫 부실 vs 반복 부실 — 검증 구간에서만 (평가 구간은 열지 않는다)
import numpy as np, pandas as pd
from hup import config, model, pipeline
df = pipeline.load()
s_, rep, fin, _ = pipeline._prepare(df)
use = pipeline._with_flags(s_, fin)
tr, va = s_["train"], s_["valid"]
ev = pd.read_csv(config.PROCESSED / "events.csv", dtype={"corp_code": str}, parse_dates=["event_date"])
print("사건 원천 기간:", ev.event_date.min().date(), "~", ev.event_date.max().date())
first = ev.groupby("corp_code")["event_date"].min()

def prior(d):
    f = d["corp_code"].map(first)
    return (f.notna() & (f <= d["rcept_dt"])).astype(int)

va = va.assign(prior=va["과거사건"]); tr = tr.assign(prior=tr["과거사건"])   # 데이터셋과 같은 정의 (labels 수정 반영)
for name, d in [("학습", tr), ("검증", va)]:
    e = d[d.y == 1]
    print(f"{name}: 사건 {len(e)} 중 과거 사건 있는 기업 {e.prior.sum()} ({e.prior.mean():.1%}) · "
          f"전체 관측치 중 과거 사건 기업 {d.prior.mean():.1%} · 그 행의 사건비율 {d.loc[d.prior==1,'y'].mean():.1%} vs 없음 {d.loc[d.prior==0,'y'].mean():.1%}")

m = model.ensemble().fit(tr[use], tr["y"])
p = pd.Series(m.predict_proba(va[use])[:, 1], index=va.index)
rows = []
for label, mask in [("검증 전체", va.prior >= 0), ("첫 부실만 (과거 사건 없는 기업)", va.prior == 0), ("반복 (과거 사건 있는 기업)", va.prior == 1)]:
    y = va.loc[mask, "y"]; r = model.evaluate(y, p[mask], n_boot=1000, groups=va.loc[mask, "corp_code"])
    base = y.mean()
    rows.append((label, int(mask.sum()), int(y.sum()), base, r["PR-AUC"], r["PR-AUC_95CI"], r["PR-AUC"]/base, r["재현율@정밀도0.3"]))
    print(f"  {label:<26} n={mask.sum():5,} 사건={int(y.sum()):3} 기준선 {base:.4f}  PR-AUC {r['PR-AUC']:.3f} {r['PR-AUC_95CI']}  {r['PR-AUC']/base:.1f}배  재현율@P0.3 {r['재현율@정밀도0.3']:.3f}")
# 민감도: 재무 데이터가 T 이후 정정본인 행을 뺀다 (docs/13 §8-3)
if "정정본재무" in va:
    for label, mask in [("첫 부실 · 정정본 제외", (va.prior == 0) & (va["정정본재무"] == 0)), ("전체 · 정정본 제외", va["정정본재무"] == 0)]:
        y = va.loc[mask, "y"]; r = model.evaluate(y, p[mask], n_boot=1000, groups=va.loc[mask, "corp_code"])
        base = y.mean()
        rows.append((label, int(mask.sum()), int(y.sum()), base, r["PR-AUC"], r["PR-AUC_95CI"], r["PR-AUC"]/base, r["재현율@정밀도0.3"]))
        print(f"  {label:<26} n={mask.sum():5,} 사건={int(y.sum()):3} 기준선 {base:.4f}  PR-AUC {r['PR-AUC']:.3f} {r['PR-AUC_95CI']}  {r['PR-AUC']/base:.1f}배  재현율@P0.3 {r['재현율@정밀도0.3']:.3f}")
# '과거 사건 여부' 하나만으로 순위를 매기면
r0 = model.evaluate(va["y"], va["prior"] + 1e-6*np.random.default_rng(0).random(len(va)), n_boot=300, groups=va["corp_code"])
print(f"  [대조] 과거 사건 여부 하나만     PR-AUC {r0['PR-AUC']:.3f} {r0['PR-AUC_95CI']}")
# 상위 1% 구성
k = int(round(len(va)*0.01)); top = p.sort_values(ascending=False).index[:k]
print(f"  상위 1% {k}곳: 실제 사건 {int(va.loc[top,'y'].sum())} · 그중 과거 사건 기업 {int(va.loc[top,'prior'].sum())}곳 (사건 중 {int(va.loc[top][va.loc[top,'y']==1].prior.sum())})")
pd.DataFrame(rows, columns=["구분","n","사건","기준선","PR-AUC","95CI","기준선대비","재현율@정밀도0.3"]).to_csv(
    config.RESULTS / "w14" / "첫부실_반복부실.csv", index=False, encoding="utf-8-sig")
