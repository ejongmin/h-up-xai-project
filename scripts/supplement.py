# 실행: PYTHONPATH=src .venv/bin/python scripts/supplement.py  (docs/10 §3-10, §3-13)
# 1) 공시 신호와 재무 상태의 중복 — 학습 구간(엠바고 적용) 원본 값 중앙값과 영업손실 비율
# 2) 업종 통제 — 업종 2자리 더미를 넣어도 검증 구간 성능이 달라지는가
import pandas as pd
from hup import config, model, pipeline
sig = pipeline.load(config.PROCESSED / "dataset_signals.csv")
s_, _, fin, _ = pipeline._prepare(sig)
tr = sig.loc[s_["train"].index]                       # 원본 값
groups = {"계속기업=1": tr["계속기업불확실성"] == 1, "제출연장=1": tr["제출기한연장"] == 1,
          "감사인교체=1": tr["감사인교체"] == 1}
none = ~(groups["계속기업=1"] | groups["제출연장=1"] | groups["감사인교체=1"])
cols = ["ROA", "이자보상배율", "부채비율", "자본잠식률"]
t = pd.DataFrame({k: tr.loc[m, cols].median() for k, m in {**groups, "신호 없음": none}.items()}).T
t["영업손실 비율"] = [tr.loc[m, "영업손실"].mean() for m in {**groups, "신호 없음": none}.values()]
t["n"] = [int(m.sum()) for m in {**groups, "신호 없음": none}.values()]
print(t.round(3).to_string()); t.round(4).to_csv(config.RESULTS / "w13" / "신호_재무중복.csv", encoding="utf-8-sig")

df = pipeline.load()
s_, _, fin, _ = pipeline._prepare(df); use = pipeline._with_flags(s_, fin)
ind = df["induty_code"].astype(str).str[:2]
top = ind[s_["train"].index].value_counts().index[:20]
dm = pd.get_dummies(ind.where(ind.isin(top), "기타"), prefix="업종", drop_first=True).astype(float)
rows = []
for label, extra in [("재무 27개 (현행)", []), ("+ 업종 더미 20개", list(dm.columns))]:
    tr_, va_ = s_["train"].join(dm), s_["valid"].join(dm)
    m = model.ensemble().fit(tr_[use + extra], tr_["y"])
    r = model.evaluate(va_["y"], m.predict_proba(va_[use + extra])[:, 1], n_boot=1000, groups=va_["corp_code"])
    rows.append({"변수 집합": label, "PR-AUC": round(r["PR-AUC"], 4), "95%CI": r["PR-AUC_95CI"]})
    print(label, round(r["PR-AUC"], 4), r["PR-AUC_95CI"])
pd.DataFrame(rows).to_csv(config.RESULTS / "w14" / "업종통제.csv", index=False, encoding="utf-8-sig")
