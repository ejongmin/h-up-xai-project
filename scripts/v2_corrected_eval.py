# 정정 평가 (docs/15 §6-2): 동결 모델 · 임계값 · 지표 그대로, 결과 미확정 행만 원칙대로 뺀다. 기존 평가결과.json 은 건드리지 않는다.
# 실행: HUP_VERSION=v2 PYTHONPATH=src .venv/bin/python scripts/v2_corrected_eval.py
import importlib.util
import json
import sys
import time

import joblib
import numpy as np
import pandas as pd
from hup import config, model

spec = importlib.util.spec_from_file_location("exp", config.ROOT / "scripts" / "v2_experiment.py")
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)

JUDGE = pd.Timestamp("2026-11-01")          # 판정일 — 이 날 공시 목록으로 개별 확인했다
EVENT_CUTOFF = pd.Timestamp("2026-09-04")   # 사건 목록 수집일
CONFIRMED = {("00120872", 2025)}            # 수집일 뒤 판정일 전에 기간이 끝나 개별 확인한 행 (§6-2 표 1행: 사건 없음 확정)
out = config.RESULTS / "final" / "정정평가결과.json"
if out.exists():
    sys.exit("정정 평가 결과가 이미 있다")
if exp.git("status", "--porcelain", "--", "src", "scripts", "docs"):
    sys.exit("작업 트리가 깨끗하지 않다 — 커밋한 뒤 실행할 것")

b = joblib.load(config.RESULTS / "freeze" / "모델.joblib")
spec_ = json.loads((config.RESULTS / "freeze" / "동결명세.json").read_text())
thr = spec_["경보 임계값"]["값"]
df, s, use = exp.frames()
assert use == b["use"]
te = s["test"]
end = te["rcept_dt"] + pd.Timedelta(config.HORIZON_DAYS, "D")
late = end > EVENT_CUTOFF
keys = list(zip(te["corp_code"], te["bsns_year"]))
unconf = [k for k, l, e in zip(keys, late, end) if l and e <= JUDGE and k not in CONFIRMED]
assert not unconf, f"수집일 뒤 판정일 전에 기간이 끝났는데 개별 확인하지 않은 행: {unconf}"
undetermined = ((end > JUDGE) & (te["y"] == 0)).to_numpy()
p = b["model"].predict_proba(te[use])[:, 1]
pc = b["calibrated"].predict_proba(te[use])[:, 1]


def block(mask):
    y, g = te["y"].to_numpy()[mask], te["corp_code"].to_numpy()[mask]
    r = model.evaluate(y, p[mask], groups=g)
    f = (p[mask] >= thr) if thr is not None else np.zeros(int(mask.sum()), bool)     # 경보 임계값이 없으면 경보 0
    tp = int((f & (y == 1)).sum())
    return {"n": int(mask.sum()), "사건": int(y.sum()), "기준선": float(y.mean()), "PR-AUC": float(r["PR-AUC"]),
            "PR-AUC_95CI": list(r["PR-AUC_95CI"]), "ROC-AUC": float(r["ROC-AUC"]), "Brier (보정 확률)": float(np.mean((pc[mask] - y) ** 2)),
            "경보 (동결 임계값)": {"경보 수": int(f.sum()), "적중": tp}}


first = (te["과거사건"] == 0).to_numpy()
allr = np.ones(len(te), bool)
groups = {"관측 기간 내 첫 부실 (주 분석)": first, "전체 (보조)": allr, "반복 부실 (보조)": ~first}
res = {"정정 전 (동결 모델로 재계산)": {k: block(m) for k, m in groups.items()},
       "정정 후 (결과 미확정 행 제외)": {k: block(m & ~undetermined) for k, m in groups.items()}}
old = json.loads((config.RESULTS / "final" / "평가결과.json").read_text())["결과"]["관측 기간 내 첫 부실 (주 분석)"]["PR-AUC"]
rec = {"성격": "정정 평가 — 모델·변수·임계값·지표 그대로, 결과 미확정 행만 제외 (docs/15 §6-2). 모델 재선택·튜닝 아님",
       "실행": time.strftime("%Y-%m-%d %H:%M:%S"), "커밋": exp.git("rev-parse", "--short", "HEAD"), "판정일": str(JUDGE.date()),
       "제외한 행": int(undetermined.sum()), "제외 사유": "판정일 현재 예측 기간(T+400일)이 끝나지 않았고 사건도 없음",
       "기존 평가결과.json 첫 부실 PR-AUC": old, "결과": res}
out.write_text(json.dumps(rec, ensure_ascii=False, indent=2, default=float))
for k, v in res.items():
    print(k, {g: (x["n"], x["사건"], round(x["PR-AUC"], 4), x["PR-AUC_95CI"], x["경보 (동결 임계값)"]) for g, x in v.items()})
print("기존 결과 첫 부실 PR-AUC", old)
