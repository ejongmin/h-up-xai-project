# 삭제 검사 그림 (2차, 검증 첫 부실): 배수만이 아니라 두 감소량을 함께 → results/v2/analysis/W11_삭제검사.png
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
t = pd.read_csv(ROOT / "results/v2/analysis/W11_삭제검사.csv")
t = t[t["대상"].str.startswith("검증 첫 부실")]
plt.rcParams["font.family"] = ["AppleGothic", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(8, 4.2), facecolor="#fcfcfb")
x, w = np.arange(len(t)), 0.38
a = ax.bar(x - w / 2, t["SHAP상위 하락"], w, color="#b5461a", label="카드가 짚은 주요 변수를 중앙값으로")
r = ax.bar(x + w / 2, t["무작위 하락"], w, color="#9aa3ae", label="무작위 변수를 중앙값으로")
for i, (sa, ra, m) in enumerate(zip(t["SHAP상위 하락"], t["무작위 하락"], t["배수"])):
    ax.text(i - w / 2, sa + 0.01, f"{sa:.3f}", ha="center", fontsize=8.5)
    ax.text(i + w / 2, ra + 0.01, f"{ra:.3f}", ha="center", fontsize=8.5, color="#4a5260")
    ax.text(i, max(sa, ra) + 0.06, f"{m}배", ha="center", fontsize=9, weight="bold")
ax.set_xticks(x, [f"{k}개" for k in t["k"]])
ax.set_xlabel("바꾼 변수 수")
ax.set_ylabel("위험 점수 평균 감소")
ax.set_ylim(0, t["SHAP상위 하락"].max() + 0.15)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.set_title("삭제 검사 — 2차 동결 모델 · 검증 구간 첫 부실 위험 상위 300건", loc="left", fontsize=11)
fig.text(0.01, 0.01, "감소가 클수록 모델이 그 변수를 근거로 쓴다는 뜻이다. 설명이 정확하다거나 원인이라는 뜻은 아니다.", fontsize=8.5, color="#4a5260")
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(ROOT / "results/v2/analysis/W11_삭제검사.png", dpi=200, facecolor="#fcfcfb")
