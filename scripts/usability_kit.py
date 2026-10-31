# 사용성 점검 준비물 (docs/16). 실행: PYTHONPATH=src .venv/bin/python scripts/usability_kit.py [참가자 수=8]
#   → results/v2/usability/배정표.csv · 기록양식.csv   (익명 — 커밋)
#   → data/usability/정답표.csv                         (기업명·원문 링크 포함 — 커밋하지 않음)
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
load = lambda f, k: json.loads((ROOT / "site" / "data" / f).read_text().split("=", 1)[1].rstrip(";\n").replace("NaN", "null"))
cards, local = load("cards_v2.js", "HUP_DATA")["cards"], load("local_names.js", "HUP_LOCAL")
# 사례 4개: 첫 부실 대상 · 설명 통과 · 요인 2개 이상 · 업종이 서로 다르게 · 순위가 너무 극단이 아닌 것부터 (시연 사례 제외)
demo = set(load("cards_v2.js", "HUP_DATA")["meta"]["demo"].values())
pool = [c for c in cards if c["group"] == "첫 부실 대상" and c["status"] == "통과" and len(c["up"]) >= 2 and c["id"] not in demo]
pick, seen = [], set()
for c in sorted(pool, key=lambda c: abs(c["rank"] - 150)):
    if c["sector"] not in seen:
        pick.append(c); seen.add(c["sector"])
    if len(pick) == 4:
        break
A, B = "순위+원문 (?mode=score)", "도구 전체"
seqs = [((0, 1), A, (2, 3), B), ((0, 1), B, (2, 3), A), ((2, 3), A, (0, 1), B), ((2, 3), B, (0, 1), A)]
rows = []
for p in range(1, n + 1):
    s1, c1, s2, c2 = seqs[(p - 1) % 4]
    for order, (cases, cond) in enumerate(((s1, c1), (s2, c2)), 1):
        for k in cases:
            rows.append({"참가자": f"P{p:02d}", "블록": order, "조건": cond, "사례": f"#{pick[k]['id']}"})
out = ROOT / "results" / "v2" / "usability"
out.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(out / "배정표.csv", index=False, encoding="utf-8-sig")
cols = ["참가자", "블록", "조건", "사례", "과제1_시간(초)", "과제1_답(위험 요인 2개)", "과제1_정답수(0~2)",
        "과제2_시간(초)", "과제2_답(근거 수치)", "과제2_정답수(0~2)", "과제3_시간(초)", "과제3_답(추가 확인 항목)", "과제3_적절(0/1)",
        "도움 요청(무엇을)", "잘못 이해한 부분(관찰)", "메모"]
pd.DataFrame([{**r, **{c: "" for c in cols[4:]}} for r in rows])[cols].to_csv(out / "기록양식.csv", index=False, encoding="utf-8-sig")
post = ["참가자", "오해1_순위가 높으면 반드시 부실(예/아니오)", "오해1_이유", "오해2_카드 요인이 부실 원인(예/아니오)", "오해2_이유",
        "이해 쉬움_A(1~5)", "이해 쉬움_B(1~5)", "근거 확인 쉬움_A(1~5)", "근거 확인 쉬움_B(1~5)", "자유 의견"]
pd.DataFrame([{c: (f"P{p:02d}" if c == "참가자" else "") for c in post} for p in range(1, n + 1)])[post].to_csv(
    out / "사후문항.csv", index=False, encoding="utf-8-sig")
pd.DataFrame([{"항목": k, "값": ""} for k in ("점검 날짜", "진행자", "화면 커밋 (git rev-parse --short HEAD)", "연습(P00) 진행 여부·고친 점")]).to_csv(
    out / "점검정보.csv", index=False, encoding="utf-8-sig")
key = []
for c in pick:
    key.append({"사례": f"#{c['id']}", "기업": local[c["id"]]["name"], "원문": local[c["id"]]["url"], "FY": c["fy"], "업종": c["sector"],
                "순위": f"{c['rank']}/{c['n_group']}",
                "과제1 정답 (모델이 위험을 높였다고 본 요인 — 이 중 2개면 정답)": " | ".join(f"{f['var']}: {f['text']}" for f in c["up"]),
                "과제2 정답 (근거 수치, 반올림 허용)": " | ".join(f"{f['var']} {f['value']}" for f in c["up"] if f["value"]),
                "과제3 적절한 답 예시": " | ".join(c["checks"] + c["notes"])})
(ROOT / "data" / "usability").mkdir(parents=True, exist_ok=True)
pd.DataFrame(key).to_csv(ROOT / "data" / "usability" / "정답표.csv", index=False, encoding="utf-8-sig")
print("사례:", [(c["id"], c["sector"], c["rank"]) for c in pick])
print(pd.DataFrame(rows).head(8).to_string(index=False))
