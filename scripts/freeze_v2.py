# 2차 최종 모델·평가 절차 동결 (docs/15 §6) — 독립 평가는 이 명세의 파일로만 한다.
# 실행: HUP_VERSION=v2 PYTHONPATH=src .venv/bin/python scripts/freeze_v2.py
#   → results/v2/freeze/동결명세.json · 전처리기준.json · 모델.joblib(압축본) · 독립평가_관측완료월.csv
#   → data/processed_v2/독립평가_대상.csv (기업 코드 포함 — 커밋하지 않고 해시만 명세에 남긴다)
import hashlib
import json
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn

from hup import config, dataset, features, pipeline

assert config.VERSION.startswith("v2")
ROOT, OUT = config.ROOT, config.RESULTS / "freeze"
git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
if git("status", "--porcelain", "--", "src", "scripts", "docs", "tests"):
    sys.exit("작업 트리가 깨끗하지 않다 — 커밋한 뒤 동결할 것")
OUT.mkdir(parents=True, exist_ok=True)

sel = json.loads((config.RESULTS / "selection" / "선택결과.json").read_text())
b = joblib.load(config.PROCESSED / "v2_final_model.joblib")
df = pipeline.load()
use_rows = df[df["검토필요"] == 0]
s = dataset.split(use_rows, horizon_days=config.HORIZON_DAYS)
fin = [c for c in features.FEATURE_COLS if c in df.columns]
st = dataset.fit_clean(s["train"], cols=fin)
clean = {k: dataset.apply_clean(v, st) for k, v in s.items()}
assert pipeline._with_flags(clean, fin) == b["use"], "변수 목록이 선택 때와 다르다"

# 전처리 기준 — 학습 구간에서 정한 값 그대로 (새 자료에도 이것만 적용)
prep = {"변수": st["cols"], "이진": st["binary"], "윈저라이즈": st["clip"], "결측더미": st["flags"],
        "하한(1%)": st["lo"].round(10).to_dict(), "상한(99%)": st["hi"].round(10).to_dict(), "대치값(중앙값)": st["med"].round(10).to_dict()}
(OUT / "전처리기준.json").write_text(json.dumps(prep, ensure_ascii=False, indent=1, default=float))

# 모델 압축본 — 같은 예측을 내는지 검증 구간에서 확인하고 묶는다.
# 2026-11-01: 숲의 병렬 합산(n_jobs=-1)은 같은 모델을 두 번 돌려도 3e-16 수준으로 달라진다 → 동결본은 단일 스레드로 예측해
# 비트 단위로 같은 결과를 낸다(임계값을 넘나드는 예측은 0건으로 확인).
for m in (b["model"], *[c.estimator for c in b["calibrated"].calibrated_classifiers_]):
    if hasattr(m, "set_params") and "clf__n_jobs" in m.get_params():
        m.set_params(clf__n_jobs=1)
joblib.dump(b, OUT / "모델.joblib", compress=3)
b2 = joblib.load(OUT / "모델.joblib")
va = clean["valid"][b["use"]]
assert np.array_equal(b["model"].predict_proba(va), b2["model"].predict_proba(va)), "압축본 예측이 다르다"
assert np.array_equal(b["calibrated"].predict_proba(va), b2["calibrated"].predict_proba(va))

# 독립 평가 대상: 분할 밖(T 가 평가 구간 뒤)의 행. 행마다 관측 완료일 = T + 400일 — 일괄 날짜가 아니다
ind = use_rows[use_rows["rcept_dt"].dt.year > config.SPLIT["test"][1]].copy()
ind["관측완료일"] = ind["rcept_dt"] + pd.Timedelta(config.HORIZON_DAYS, "D")
ind[["corp_code", "bsns_year", "rcept_dt", "관측완료일", "과거사건"]].to_csv(config.PROCESSED / "독립평가_대상.csv", index=False)
by = (ind.assign(월=ind["관측완료일"].dt.strftime("%Y-%m")).groupby("월")
      .agg(행=("corp_code", "size"), 첫부실_대상=("과거사건", lambda x: int((x == 0).sum()))).reset_index())
by["누적 행"] = by["행"].cumsum()
by.to_csv(OUT / "독립평가_관측완료월.csv", index=False, encoding="utf-8-sig")

files = ["src/hup/" + f for f in ("config.py", "dart.py", "xbrl.py", "checks.py", "labels.py", "features.py", "dataset.py",
                                  "pipeline.py", "model.py", "explain.py")] + ["scripts/v2_experiment.py", "docs/15_2차연구_계획_사전고정.md"]
spec = {
    "동결": git("log", "-1", "--format=%cs"), "커밋": git("rev-parse", "HEAD"),
    "성격": "2차 최종 모델·평가 절차. 독립 평가는 이 명세의 파일과 규칙으로만 한다 (docs/15 §6).",
    "환경": {"예측": "단일 스레드(n_jobs=1) — 병렬 합산 오차(약 3e-16) 없이 재현", "python": sys.version.split()[0], "scikit-learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__,
             "주의": "joblib 은 scikit-learn 판에 묶인다 — 같은 판에서 불러올 것"},
    "학습 데이터": {"dataset.csv sha256": sha(config.PROCESSED / "dataset.csv"), "MANIFEST": json.loads((config.PROCESSED / "MANIFEST.json").read_text()),
                "학습 표본": {"n": len(s["train"]), "사건": int(s["train"]["y"].sum()), "규칙": "T 2016~2021 중 T+400일 < 2022-01-01 (엠바고), 검토필요=0"}},
    "전처리": {"파일": "results/v2/freeze/전처리기준.json", "sha256": sha(OUT / "전처리기준.json"),
               "규칙": "학습 구간 1·99% 윈저라이즈(이진 제외) → 중앙값 대치 → 결측 더미 (dataset.fit_clean/apply_clean)"},
    "변수": b["use"],
    "모델": {"이름": b["chosen"], "설정": b["config"], "파일": "results/v2/freeze/모델.joblib", "sha256": sha(OUT / "모델.joblib"),
             "선택 때 원본 sha256(16)": sel["모델 파일 sha256(16)"], "확률 보정": "같은 묶음의 calibrated (isotonic 5겹, 같은 학습 표본) — 첫 부실 집단에서 보정 불량(§6-1), 표시하지 않는다"},
    "경보 임계값": {"값": sel["경보 임계값 (검증 첫 부실, 정밀도 30% 이상인 가장 낮은 점수)"], "점수": "model.predict_proba[:,1] (비보정)",
                "정한 곳": "검증 구간 첫 부실, 정밀도 30% 이상인 가장 낮은 점수"},
    "평가 규칙": {"주 지표": "관측 기간 내 첫 부실 집단 PR-AUC (기준선 = 그 집단 사건비율), 기업 군집 부트스트랩 95% 구간 1,000회 (시드 0)",
                "경보 성능": "동결 임계값을 그대로 적용한 정밀도·재현율", "사건 정의": "docs/15 §2 (감사의견 비적정 · 회생절차 개시 신청, T 이후 400일)",
                "과거사건": "T 시점까지 관측된 첫 사건일 ≤ T", "재학습·재선택·임계값 조정 금지": True},
    "독립 평가": {"대상": "T 가 2026년 이후인 행 (개발에 쓰지 않음)", "행": len(ind), "첫 부실 대상": int((ind["과거사건"] == 0).sum()),
                "대상 목록 sha256": sha(config.PROCESSED / "독립평가_대상.csv"),
                "관측 완료일": "행마다 T + 400일. 공개가 늦은 공시는 완료도 늦다 (results/v2/freeze/독립평가_관측완료월.csv)",
                "가장 이른 완료": str(ind["관측완료일"].min().date()), "가장 늦은 완료": str(ind["관측완료일"].max().date()),
                "평가 시점 규칙": "평가일 기준 관측 완료된 행만 포함하고, 사건 목록을 그 완료일 이후에 다시 수집한 뒤 평가한다. 미완료 행은 수를 보고하고 제외한다."},
    "코드 파일 sha256": {f: sha(ROOT / f) for f in files},
    "선택 결과": {"파일": "results/v2/selection/선택결과.json", "sha256": sha(config.RESULTS / "selection" / "선택결과.json")},
    "수정 후 재평가": {"파일": "results/v2/final/평가결과.json", "sha256": sha(config.RESULTS / "final" / "평가결과.json")},
}
(OUT / "동결명세.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2, default=float))
print(json.dumps({k: spec[k] for k in ("커밋", "모델", "독립 평가")}, ensure_ascii=False, indent=1))
print(by.to_string(index=False))
