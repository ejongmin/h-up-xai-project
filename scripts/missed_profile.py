# 실행: PYTHONPATH=src .venv/bin/python scripts/missed_profile.py  (docs/10 §3-9)
# 검증 구간 보정 확률 상위 5% 를 고위험으로 보고, 미탐·정탐·정상의 원본 재무값 중앙값을 비교한다 (w12 와 같은 임계).
import pandas as pd
from hup import config, model, pipeline
raw = pipeline.load()
s_, _, fin, _ = pipeline._prepare(raw)
use = pipeline._with_flags(s_, fin)
tr, va = s_["train"], s_["valid"]
cal = model.calibrated(model.ensemble, "isotonic").fit(tr[use], tr["y"])
p = pd.Series(cal.predict_proba(va[use])[:, 1], index=va.index)
hi = p.quantile(0.95)
r = raw.loc[va.index]                    # 정제(윈저라이즈) 전 원본 값
grp = pd.Series("정상", index=va.index)
grp[(va.y == 1) & (p < hi)] = "미탐"
grp[(va.y == 1) & (p >= hi)] = "정탐"
cols = ["ROA", "이자보상배율", "부채비율", "유동비율", "자본잠식률"]
rows = []
for sub, mask in [("전체", va.index == va.index), ("첫 부실", va["과거사건"] == 0)]:
    t = r[mask].groupby(grp[mask])[cols].median().T[["미탐", "정탐", "정상"]]
    n = grp[mask].value_counts()
    print(f"[{sub}] 임계 {hi:.3f} · 미탐 {n.get('미탐',0)} · 정탐 {n.get('정탐',0)}")
    print(t.round(3).to_string())
    t.columns = [f"{sub}_{c}" for c in t.columns]; rows.append(t)
pd.concat(rows, axis=1).round(4).to_csv(config.RESULTS / "w12" / "미탐정탐_재무중앙값.csv", encoding="utf-8-sig")
