# 실행: PYTHONPATH=src .venv/bin/python scripts/figure_main.py   → results/final/대표그림.png
# 대표 그림: 전체 성능과 '관측 기간 내 첫 부실' 성능을 나란히, 왜 다른지(반복 부실 비중)와 함께.
# 수치는 결과 파일에서 읽는다 — 손으로 옮기지 않는다.
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from hup import config

fin = json.loads((config.RESULTS / "final" / "최종성능.json").read_text())["결과"]
val = pd.read_csv(config.RESULTS / "w14" / "첫부실_반복부실.csv", encoding="utf-8-sig").set_index("구분")

def ci(x):
    return [float(v) for v in (x if isinstance(x, list) else str(x).strip("()").split(","))]

panels = {
    "검증 구간 2022~2023 (참고)": [
        ("관측 기간 내\n첫 부실 (주 분석)", val.loc["첫 부실만 (과거 사건 없는 기업)"]),
        ("반복 부실", val.loc["반복 (과거 사건 있는 기업)"]),
        ("전체", val.loc["검증 전체"]),
    ],
    "평가 구간 2024~2025 (오류 수정 후 재평가)": [
        ("관측 기간 내\n첫 부실 (주 분석)", fin["관측 기간 내 첫 부실 (주 분석)"]),
        ("반복 부실", fin["반복 부실 (보조)"]),
        ("전체", {**fin["앙상블(비보정)"], "기준선": fin["기준선"], "사건": fin["앙상블(비보정)"]["사건수"]}),
    ],
}
# 반복 부실 비중도 결과 파일에서 계산한다 (2026-10-13: 손으로 적어 둔 문구가 재평가 뒤에 낡아 있었다)
def share_text(rep, tot):
    r, t = int(rep["사건"]), int(tot["사건"])
    return f"사건 {t}건 중 {r}건({r / t:.0%})이 반복 부실"
share = {t: share_text(items[1][1], items[2][1]) for t, items in panels.items()}
COL = {"관측 기간 내\n첫 부실 (주 분석)": "#2a78d6", "반복 부실": "#eb6834", "전체": "#8a8984"}
INK, MUTED, SURF = "#0b0b0b", "#52514e", "#fcfcfb"

plt.rcParams["font.family"] = ["AppleGothic", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
# 평가 구간이 본문, 검증 구간은 보조 — 폭으로 위계를 준다 (2026-10-18 발표 검토)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, facecolor=SURF, gridspec_kw={"width_ratios": [1, 1.6]})
for ax, (title, items) in zip(axes, panels.items()):
    ax.set_facecolor(SURF)
    for k, (name, r) in enumerate(items):
        p = float(r["PR-AUC"]); lo, hi = ci(r["PR-AUC_95CI"] if "PR-AUC_95CI" in r else r["95CI"])
        base = float(r["기준선"])
        ax.bar(k, p, width=0.56, color=COL[name], alpha=1 if ax is axes[1] else 0.45, zorder=2)
        ax.errorbar(k, p, yerr=[[p - lo], [hi - p]], color=INK, lw=1, capsize=4, zorder=3)
        ax.hlines(base, k - 0.34, k + 0.34, colors=INK, linestyles=(0, (3, 2)), lw=1.2, zorder=4)
        ax.text(k, hi + 0.02, f"{p:.3f}\n기준선의 {p / base:.1f}배", ha="center", va="bottom", fontsize=9.5, color=INK)
    ax.set_xticks(range(3), [n for n, _ in items], fontsize=10, color=INK)
    ax.set_title(title, fontsize=11, color=INK if ax is axes[1] else MUTED, loc="left")
    ax.text(0, -0.26, share[title], transform=ax.transAxes, fontsize=9.5, color=MUTED)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#c9c8c2"); ax.spines["bottom"].set_color("#c9c8c2")
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color="#e6e5e0", lw=0.8, zorder=0)
axes[0].set_ylabel("PR-AUC", fontsize=10, color=MUTED)
axes[0].set_ylim(0, 0.95)
fig.suptitle("부실 예측 모델은 무엇을 맞히는가 — 높은 전체 성능의 상당 부분은 이미 부실을 겪은 기업에서 나온다",
             fontsize=12, color=INK, x=0.01, ha="left")
fig.text(0.01, 0.015, "막대: 추정치 · 수염: 부트스트랩 95% 신뢰구간 · 점선: 그 집단의 사건비율(무작위 순위의 기대 PR-AUC). 단위: 기업-연도 관측치. 2015년 이전 부실 이력은 관측되지 않음.",
         fontsize=9, color=MUTED)
fig.tight_layout(rect=(0, 0.07, 1, 0.95))
out = config.RESULTS / "final" / "대표그림.png"
fig.savefig(out, dpi=200, facecolor=SURF)
print("저장:", out)
