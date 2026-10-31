# 설명 카드 사이트 데이터: site/data/cards_<판>.js  (docs/15 §7)
# 실행: PYTHONPATH=src .venv/bin/python scripts/site_data.py        (HUP_VERSION=v2 면 2차 데이터)
#
# 검증 구간 · 위험 상위 10% (첫 부실 집단 · 이력 있는 집단 각각) 의 카드를 구조화해 내보낸다.
# 익명: 기업명·종목코드·고유번호를 넣지 않는다. 업종은 대분류, 사례 번호는 순위와 무관하게 섞는다.
# file:// 로 열어도 되도록 JSON 이 아니라 전역 변수에 담은 JS 로 쓴다.
import json
import random

import numpy as np
import pandas as pd
from hup import config, explain, model, pipeline

raw = pipeline.load()
s_, _, fin, _ = pipeline._prepare(raw)
use = pipeline._with_flags(s_, fin)
tr, va = s_["train"], s_["valid"]
est = model.ensemble().fit(tr[use], tr["y"])
cal = model.calibrated(model.ensemble, "isotonic").fit(tr[use], tr["y"])
allow = explain.stable_features(lambda random_state: model.ensemble(random_state=random_state),
                                tr[use], tr["y"], top=len(use))
ref = tr[use].median()
train_raw = raw.loc[tr.index]


def sector(code):
    """업종 대분류 (KSIC 앞 2자리). 사례가 특정되지 않도록 넓게 묶는다."""
    try:
        k = int(str(code)[:2])
    except ValueError:
        return "기타"
    for lo, hi, name in ((10, 34, "제조업"), (58, 63, "정보통신업"), (45, 47, "도소매업"), (41, 42, "건설업"),
                         (70, 73, "전문·과학·기술"), (49, 52, "운수·창고"), (86, 87, "보건·복지"), (35, 39, "전기·수도·환경")):
        if lo <= k <= hi:
            return name
    return "기타"


def pct_rank(name, v):
    """학습 구간 원자료에서의 위치 (0~100). 표본 내 위치 막대용."""
    col = train_raw[name].dropna() if name in train_raw else pd.Series(dtype=float)
    if v is None or pd.isna(v) or col.empty:
        return None
    return round(float((col < v).mean() * 100), 1)


def factor(row, name, contrib):
    unit = explain.PHRASE.get(name, ("", "", ""))[2]
    v = row.get(name)
    return {"var": name, "text": explain.sentence(name, v, ref, contrib),
            "value": "" if name in explain.FLAGS else explain.format_value(name, v, unit).strip(" ()").replace("실측 ", ""),
            "shap": round(float(contrib), 3), "pct": pct_rank(name, v),
            "risky_high": name in explain.HIGH_IS_RISKY,
            "median": explain.format_value(name, ref.get(name), unit).strip(" ()").replace("실측 ", "") if name in ref else ""}


def build(group_mask, group_name):
    part = va[group_mask]
    X = part[use]
    rank = pd.Series(est.predict_proba(X)[:, 1], index=part.index).sort_values(ascending=False)
    prob = pd.Series(cal.predict_proba(X)[:, 1], index=part.index)
    top = rank.index[: int(len(rank) * 0.10)]
    sv = pd.DataFrame(explain.shap_values(est, X.loc[top]), index=top, columns=use)
    out = []
    for r_i, ix in enumerate(top, 1):
        row, v = raw.loc[ix], sv.loc[ix]
        wiped = explain._equity_wiped(row)
        why = explain.hold_reasons(row, v.to_numpy(), use, allow, ref)
        s = explain._shown(v, allow, wiped)
        up = s[s > 0].sort_values(ascending=False).head(4)
        down = s[s < 0].sort_values().head(2)
        fixed = [{"var": n, "old": explain.PHRASE[n][0], "new": explain.ABS_CUT[n][1]}
                 for n in up.index if explain._risky_side(n, row.get(n), ref) and explain.overstated(n, row.get(n))]
        cf = []
        if not why:
            base, items = explain.counterfactual(cal, X.loc[ix], use, list(up.index), ref,
                                                 skip=explain.EQUITY_BASED if wiped else ())
            cf = [{"phrase": ph, "from": round(b, 4), "to": round(p, 4)} for _n, b, p, _t, ph in items]
        out.append({
            "fy": int(row["bsns_year"]), "sector": sector(row.get("induty_code")), "group": group_name,
            "y": int(row["y"]), "prob": round(float(prob[ix]), 4),
            "rank": r_i, "rank_pct": round(100 * r_i / len(rank), 1), "n_group": len(rank),
            "status": "보류" if why else ("교정" if fixed else "통과"),
            "hold": why, "wiped": bool(wiped), "fixed": fixed,
            "up": [factor(row, n, c) for n, c in up.items()] if not why else [],
            "down": [factor(row, n, c) for n, c in down.items()] if not why else [],
            "top_model": [{"var": n, "shap": round(float(v[n]), 3)} for n in v.abs().sort_values(ascending=False).index[:5]],
            "cf": cf,
        })
    return out


cards = build(va["과거사건"] == 0, "첫 부실 후보") + build(va["과거사건"] == 1, "부실 이력 있음")
random.Random(20261031).shuffle(cards)                 # 사례 번호가 순위를 드러내지 않게
for i, c in enumerate(cards, 1):
    c["id"] = f"{i:03d}"
meta = {"판": config.VERSION, "구간": "검증 2022~2023 (T 연도)", "선정": "집단별 위험 상위 10%",
        "카드수": len(cards), "원천": "1차 탐색 연구 — 최신 정정본 재무" if config.VERSION == "v1" else "2차 — 최초 공시 원본 XBRL",
        "보정": "isotonic (두 집단 합쳐 보정, 집단별 보정 미확인)"}
d = config.ROOT / "site" / "data"
d.mkdir(parents=True, exist_ok=True)
(d / f"cards_{config.VERSION}.js").write_text(
    "window.HUP_DATA = " + json.dumps({"meta": meta, "cards": cards}, ensure_ascii=False, default=lambda o: None if isinstance(o, float) and np.isnan(o) else o) + ";\n")
print(meta, pd.Series([c["status"] for c in cards]).value_counts().to_dict())
