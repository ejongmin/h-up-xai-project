# 실행: PYTHONPATH=src .venv/bin/python scripts/demo_cards.py   → results/demo/세_사례.md
# 시연 세 장 (검증 구간, 관측 기간 내 첫 부실 집단, 익명):
#   ① 정상 카드  ② 잘못된 단정이 고쳐진 카드(구 방식 vs 현행)  ③ 설명을 보류한 카드
# 각 사례마다: 원자료 → 모델 판단 → 설명 검사 → 카드(또는 보류 사유).
import numpy as np
import pandas as pd
from hup import config, explain, model, pipeline

raw = pipeline.load()
s_, _, fin, _ = pipeline._prepare(raw)
use = pipeline._with_flags(s_, fin)
tr, va = s_["train"], s_["valid"]
est = model.ensemble().fit(tr[use], tr["y"])
cal = model.calibrated(model.ensemble, "isotonic").fit(tr[use], tr["y"])
first = va[va["과거사건"] == 0]
X = first[use]
rank = pd.Series(est.predict_proba(X)[:, 1], index=first.index).sort_values(ascending=False)
prob = pd.Series(cal.predict_proba(X)[:, 1], index=first.index)
sv = pd.DataFrame(explain.shap_values(est, X), index=first.index, columns=use)
allow = explain.stable_features(lambda random_state: model.ensemble(random_state=random_state),
                                tr[use], tr["y"], top=len(use))
ref = tr[use].median()


def overstated_lines(row, s):
    s = explain._shown(s, allow, explain._equity_wiped(row))
    up = s[s > 0].sort_values(ascending=False).head(4)
    return [n for n in up.index if explain._risky_side(n, row.get(n), ref) and explain.overstated(n, row.get(n))]


def old_card(row, v, p):
    """2026-10-10 이전 방식(ABS_CUT 없음)으로 만든 카드 — 비교용."""
    keep = dict(explain.ABS_CUT)
    explain.ABS_CUT.clear()
    try:
        return explain.card(row, v, use, allow=allow, ref=ref, prob=p, hold=False)
    finally:
        explain.ABS_CUT.update(keep)


pick = {}
top10 = list(rank.index[: int(len(rank) * 0.10)])
# 정상·교정 사례는 실제 사건 기업을 먼저 고른다 (없으면 사건 없는 기업)
for ix in [i for i in top10 if raw.loc[i, "y"] == 1] + [i for i in top10 if raw.loc[i, "y"] == 0]:
    row, v = raw.loc[ix], sv.loc[ix].to_numpy()
    why = explain.hold_reasons(row, v, use, allow, ref)
    over = overstated_lines(row, sv.loc[ix])
    if why and "보류" not in pick:
        pick["보류"] = ix
    elif not why and over and "교정" not in pick:
        pick["교정"] = ix
    elif not why and not over and "정상" not in pick:
        pick["정상"] = ix
    if len(pick) == 3:
        break

out = ["# 설명 카드 시연 — 세 사례", "",
       "검증 구간 · **관측 기간 내 첫 부실 집단**(과거 관측된 부실 이력 없음) · 위험 상위 10% 안에서 고름 · 익명.",
       "재현: `PYTHONPATH=src .venv/bin/python scripts/demo_cards.py`", ""]
title = {"정상": "① 정상 카드 — 검사를 모두 통과", "교정": "② 잘못된 단정이 고쳐진 카드", "보류": "③ 설명을 보류한 카드"}
for key in ("정상", "교정", "보류"):
    ix = pick[key]
    row, v = raw.loc[ix], sv.loc[ix]
    s = explain._shown(v, allow, explain._equity_wiped(row))
    top = v.abs().sort_values(ascending=False).head(5)
    out += [f"## {title[key]}", "",
            f"**원자료** — FY{int(row['bsns_year'])} · 실제 사건 {'있음' if row['y'] == 1 else '없음'} (T 이후 400일 안)", "",
            "| 변수 | 원본 값 | 학습 구간 중앙값 |", "|---|---|---|"]
    for n in top.index:
        b = n.replace("_결측", "")
        out.append(f"| {n} | {row.get(b) if n.endswith('_결측') else row.get(n):.4g} | "
                   f"{ref[n] if n in ref else float('nan'):.4g} |")
    out += ["", f"**모델 판단** — 보정 확률 {prob[ix]:.1%} · 집단 내 순위 {list(rank.index).index(ix) + 1}/{len(rank)} · "
            f"가장 큰 근거(SHAP, +는 위험을 올림): {', '.join(f'{n} {v[n]:+.2f}' for n in top.index[:3])}", ""]
    why = explain.hold_reasons(row, v.to_numpy(), use, allow, ref)
    over = overstated_lines(row, v)
    out += ["**설명 검사**", "",
            f"- 단위 의심: {'걸림' if any(w.startswith('단위') for w in why) else '통과'}",
            f"- 핵심값 결측: {'걸림' if any(w.startswith('핵심값') for w in why) else '통과'}",
            f"- 설명 불안정: {'걸림' if any(w.startswith('설명 불안정') for w in why) else '통과'}",
            f"- 문장 방향 충돌: {'걸림' if any(w.startswith('문장 방향') for w in why) else '통과'}",
            f"- 사실 단정 (구 방식이면 틀렸을 문장): {', '.join(over) if over else '없음'}", ""]
    if key == "교정":
        out += ["**구 방식 카드** (2026-10-10 이전)", "```", old_card(row, v.to_numpy(), prob[ix]), "```", "",
                "**현행 카드**", "```", explain.card(row, v.to_numpy(), use, allow=allow, ref=ref, prob=prob[ix]), "```", ""]
    else:
        out += ["**카드**", "```", explain.card(row, v.to_numpy(), use, allow=allow, ref=ref, prob=prob[ix]), "```", ""]
d = config.RESULTS / "demo"; d.mkdir(parents=True, exist_ok=True)
(d / "세_사례.md").write_text("\n".join(out))
print("\n".join(out))
