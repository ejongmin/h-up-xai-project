# 실행: PYTHONPATH=src .venv/bin/python scripts/explain_audit.py   (docs/10 §3-8b) — 검증 구간에서만
# 설명 검증을 주 분석(관측 기간 내 첫 부실)에 맞춰 집단별로 다시 낸다.
#  [A] 실제 사례: 집단(과거 부실 이력 없음/있음) × 범위(검증 전체 / 집단 내 위험 상위 10%)
#      카드에 오른 줄 중 '구 방식이면 사실과 다른 단정' 비율, 설명 보류율, 보류 사유
#  [B] 인위적 사례: 보류되지 않은 실제 카드에 오류를 하나씩 넣어 보류가 걸리는지 (탐지율)
# 실제 사례와 인위적 사례는 섞지 않는다.
import numpy as np
import pandas as pd
from hup import config, explain, model, pipeline

raw = pipeline.load()
s_, _, fin, _ = pipeline._prepare(raw)
use = pipeline._with_flags(s_, fin)
tr, va = s_["train"], s_["valid"]
est = model.ensemble().fit(tr[use], tr["y"])
X = va[use]
rank = pd.Series(est.predict_proba(X)[:, 1], index=va.index)
sv = explain.shap_values(est, X)
allow = explain.stable_features(lambda random_state: model.ensemble(random_state=random_state),
                                tr[use], tr["y"], top=len(use))
ref = tr[use].median()
pos = {ix: k for k, ix in enumerate(va.index)}


def lines(row, s):
    """card() 와 같은 규칙으로 실제 카드에 오르는 줄 (위험 4 + 낮춘 2)."""
    s = explain._shown(s, allow, explain._equity_wiped(row))
    return list(s[s > 0].sort_values(ascending=False).head(4).index) + list(s[s < 0].sort_values().head(2).index)


def audit(idx):
    n_line = n_over = n_hold = 0
    why = {}
    for ix in idx:
        row, s = raw.loc[ix], pd.Series(sv[pos[ix]], index=use)
        w = explain.hold_reasons(row, sv[pos[ix]], use, allow, ref)
        if w:
            n_hold += 1
            for x in w:
                why[x.split(" — ")[0]] = why.get(x.split(" — ")[0], 0) + 1
            continue
        for nm in lines(row, s):
            n_line += 1
            n_over += bool(explain._risky_side(nm, row.get(nm), ref)) and explain.overstated(nm, row.get(nm))
    return {"카드": len(idx), "카드 줄": n_line, "사실 오류 줄(구 방식)": n_over,
            "사실 오류율(구 방식)": round(n_over / max(n_line, 1), 4), "사실 오류율(현행)": 0.0,
            "보류": n_hold, "보류율": round(n_hold / max(len(idx), 1), 4),
            "보류 사유": "; ".join(f"{k} {v}" for k, v in sorted(why.items(), key=lambda x: -x[1])) or "—"}


rows = []
for g_name, g in [("과거 부실 이력 없음 (주 분석)", va["과거사건"] == 0), ("과거 부실 이력 있음", va["과거사건"] == 1)]:
    gi = va.index[g]
    top = rank[gi].sort_values(ascending=False).index[: max(1, int(len(gi) * 0.10))]
    for scope, idx in [("검증 전체", gi), ("집단 내 위험 상위 10%", top)]:
        rows.append({"집단": g_name, "범위": scope, **audit(idx)})
A = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print("[A] 실제 사례 (검증 구간)\n", A.to_string(index=False))

# [B] 인위적 사례 — 보류되지 않은 실제 카드(위험 상위 10%, 두 집단 합)에 오류를 하나씩 넣는다
base = [ix for ix in rank.sort_values(ascending=False).index[: int(len(va) * 0.10)]
        if not explain.hold_reasons(raw.loc[ix], sv[pos[ix]], use, allow, ref)]
flags = [c for c in use if c.endswith("_결측")]
res = {}
for ix in base:
    row, v = raw.loc[ix].copy(), sv[pos[ix]].copy()
    s = explain._shown(pd.Series(v, index=use), allow, explain._equity_wiped(row))
    up = s[s > 0].sort_values(ascending=False)
    if not len(up):
        continue
    t1 = up.index[0]
    cases = {}
    r1 = row.copy(); r1["_assets"] = 3e8; cases["단위 오류 (자산 3억 원)"] = (r1, v)
    r2 = row.copy(); r2[t1] = np.nan; cases["핵심값 누락 (위험 요인 1위 값 삭제)"] = (r2, v)
    v3 = v.copy(); v3[use.index(flags[0])] = np.abs(v).max() * 2; cases["설명 불안정 (결측 더미가 최대 근거)"] = (row, v3)
    r4 = row.copy()
    hi = t1 in explain.HIGH_IS_RISKY
    r4[t1] = (ref[t1] - abs(ref[t1]) - 1) if hi else (ref[t1] + abs(ref[t1]) + 1)
    cases["방향 충돌 (위험 요인 1위를 안전 쪽 값으로)"] = (r4, v)
    for k, (r, vv) in cases.items():
        hit = bool(explain.hold_reasons(r, vv, use, allow, ref))
        a = res.setdefault(k, [0, 0]); a[0] += hit; a[1] += 1
B = pd.DataFrame([{"넣은 오류": k, "사례": n, "보류됨": h, "탐지율": round(h / n, 4)} for k, (h, n) in res.items()])
print(f"\n[B] 인위적 사례 — 보류되지 않은 실제 카드 {len(base)}건에 오류를 하나씩 넣음\n", B.to_string(index=False))
out = config.RESULTS / "w11"
A.to_csv(out / "설명검증_집단별.csv", index=False, encoding="utf-8-sig")
B.to_csv(out / "설명보류_인위오류.csv", index=False, encoding="utf-8-sig")
print(f"\n저장: {out}/설명검증_집단별.csv · 설명보류_인위오류.csv")
