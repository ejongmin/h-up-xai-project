# 1차(최신 정정본 API) vs 2차(최초 공시 원본 XBRL) 재무값 대조 — 성능은 보지 않는다 (docs/15 §3).
# 실행: PYTHONPATH=src .venv/bin/python scripts/compare_v1_v2.py  → results/v2/data_check/v1_v2_대조.csv
import numpy as np
import pandas as pd
from hup import config, features

v1 = pd.read_csv(config.DATA / "processed" / "dataset.csv", dtype={"corp_code": str})
v2 = pd.read_csv(config.PROCESSED / "dataset.csv", dtype={"corp_code": str})
k = ["corp_code", "bsns_year"]
m = v1.merge(v2, on=k, how="outer", suffixes=("_1", "_2"), indicator=True)
print("행 대응:", m["_merge"].value_counts().to_dict())
both = m[m["_merge"] == "both"]
cols = ["_assets", "_revenue"] + [c for c in features.FEATURE_COLS if not c.startswith("Δ") and not c.endswith("증가율") and c != "2년연속영업손실"]
rows = []
for c in cols:
    a, b = both[f"{c}_1"], both[f"{c}_2"]
    has = a.notna() & b.notna()
    same = has & (np.isclose(a, b, rtol=1e-3, atol=1e-9))
    for name, g in (("전체", both.index), ("1차 정정본재무=1", both.index[both["정정본재무_1"] == 1]), ("1차 정정본재무=0", both.index[both["정정본재무_1"] == 0])):
        h = has.loc[g]
        rows.append({"변수": c, "집단": name, "둘다값": int(h.sum()), "일치율": round(float(same.loc[g].sum() / max(h.sum(), 1)), 4),
                     "1차만결측": int((a.loc[g].isna() & b.loc[g].notna()).sum()), "2차만결측": int((a.loc[g].notna() & b.loc[g].isna()).sum())})
t = pd.DataFrame(rows)
out = config.RESULTS / "data_check"
out.mkdir(parents=True, exist_ok=True)
t.to_csv(out / "v1_v2_대조.csv", index=False, encoding="utf-8-sig")
print(t.pivot(index="변수", columns="집단", values="일치율").to_string())
print(t[t["집단"] == "전체"][["변수", "1차만결측", "2차만결측"]].to_string(index=False))
print("라벨 일치:", float((both["y_1"] == both["y_2"]).mean()), "사건 1차/2차:", int(both["y_1"].sum()), int(both["y_2"].sum()))
