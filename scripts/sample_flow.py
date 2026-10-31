# 표본 흐름표: 1차 → 원본 확보 → 2차 → 학습·평가 대상 (docs/15 §3-2). 성능은 보지 않는다.
# 실행: PYTHONPATH=src .venv/bin/python scripts/sample_flow.py → results/v2/data_check/표본흐름.csv
import pandas as pd
from hup import config, dart, xbrl

k = ["corp_code", "bsns_year"]
v1 = pd.read_csv(config.DATA / "processed" / "dataset.csv", dtype={"corp_code": str}, parse_dates=["rcept_dt"])
v2 = pd.read_csv(config.DATA / "processed_v2" / "dataset.csv", dtype={"corp_code": str}, parse_dates=["rcept_dt"])
ff = dart.first_filings()
unc = pd.read_csv(config.ROOT / "results" / "v2" / "data_check" / "시점확인불가.csv", dtype={"corp_code": str})
has = v1.apply(lambda r: xbrl.fetch(ff[(r.corp_code, r.bsns_year)][0]) is not None, axis=1)
key1, key2 = set(zip(v1.corp_code, v1.bsns_year)), set(zip(v2.corp_code, v2.bsns_year))
new = v2[[t not in key1 for t in zip(v2.corp_code, v2.bsns_year)]]
gone = v1[has & pd.Series([t not in key2 for t in zip(v1.corp_code, v1.bsns_year)], index=v1.index)]
# 2차에만 있는 행: 1차는 API 재무가 비어 패널에서 빠졌던 행인가
api_empty = sum(not dart.financials(c, int(y))[0] for c, y in zip(new.corp_code, new.bsns_year))
both = v1.merge(v2, on=k, suffixes=("_1", "_2"))
use = v2[v2["검토필요"] == 0]
yr = use["rcept_dt"].dt.year
part = {p: use[(yr >= a) & (yr <= b)] for p, (a, b) in config.SPLIT.items()}
rows = [
    ("1차 데이터셋", len(v1), int(v1.y.sum()), ""),
    ("  원본 XBRL 없음", int((~has).sum()), int(v1[~has].y.sum()), "주 분석 제외"),
    ("  원본 확보", int(has.sum()), int(v1[has].y.sum()), ""),
    ("    그중 최초 공개 자료 확인 불가(재등록 파일)", len(gone), int(gone.y.sum()), f"주 분석 제외 — {len(unc)}건 목록"),
    ("    1차·2차 모두 있는 행", len(both), int(both.y_2.sum()), f"라벨 일치 {float((both.y_1 == both.y_2).mean()):.1%}"),
    ("  2차에만 있는 행", len(new), int(new.y.sum()), f"1차 API 재무 응답이 비어 빠졌던 행 {api_empty}건"),
    ("2차 데이터셋", len(v2), int(v2.y.sum()), "= 양쪽 모두 + 2차에만"),
    ("  검토 대상 (단위 의심)", int(v2["검토필요"].sum()), int(v2.loc[v2["검토필요"] == 1, "y"].sum()), "판정 전까지 학습·평가 제외"),
    ("학습·평가 후보", len(use), int(use.y.sum()), ""),
]
for p, d in part.items():
    f = d[d["과거사건"] == 0]
    rows.append((f"  {p} ({config.SPLIT[p][0]}~{config.SPLIT[p][1]})", len(d), int(d.y.sum()), f"첫 부실 집단 {len(f):,}행 · 사건 {int(f.y.sum())}"))
pre = use[yr < config.SPLIT["train"][0]]
rows.append((f"  분할 앞 (T ~{config.SPLIT['train'][0] - 1})", len(pre), int(pre.y.sum()), "변화량 계산용 첫해 — 학습·평가에 쓰지 않음"))
rest = use[yr > config.SPLIT["test"][1]]
rows.append((f"  분할 밖 (T {config.SPLIT['test'][1] + 1}~)", len(rest), int(rest.y.sum()), "독립 평가 후보 — 결과 관측 미완료 (docs/15 §6)"))
t = pd.DataFrame(rows, columns=["단계", "행", "사건", "비고"])
t.to_csv(config.ROOT / "results" / "v2" / "data_check" / "표본흐름.csv", index=False, encoding="utf-8-sig")
print(t.to_string(index=False))
