# 기업 위험 검토 도구(site/) 데이터 — 2차 동결 모델 (docs/15 §6-1, §7)
# 실행: HUP_VERSION=v2 PYTHONPATH=src .venv/bin/python scripts/site_data_v2.py
#   → site/data/cards_v2.js        공개용 (익명: 기업명·종목코드·고유번호·정확한 공시일 없음)
#   → site/data/local_names.js     로컬 전용 (기업명 + DART 원문 링크, .gitignore — 발표 노트북에서만)
#
# 평가 구간(T 2024~2025, 이미 1회 평가를 마친 구간)에서 집단별 위험 상위 10% 의 카드.
# 확률은 싣지 않는다 — 첫 부실 집단에서 보정 확률의 Brier 가 상수 예측보다 나빴다(§6-1). 집단 내 순위로 보여준다.
import json
import random

import joblib
import numpy as np
import pandas as pd
from hup import config, dataset, explain, features, model, pipeline

assert config.VERSION.startswith("v2")
b = joblib.load(config.RESULTS / "freeze" / "모델.joblib")      # 동결본
sel = json.loads((config.RESULTS / "selection" / "선택결과.json").read_text())
ev_res = json.loads((config.RESULTS / "final" / "평가결과.json").read_text())
use, cfg = b["use"], b["config"]

raw = pipeline.load()
raw = raw[raw["검토필요"] == 0]
s = dataset.split(raw, horizon_days=config.HORIZON_DAYS)
fin = [c for c in features.FEATURE_COLS if c in raw.columns]
st = dataset.fit_clean(s["train"], cols=fin)
clean = {k: dataset.apply_clean(v, st) for k, v in s.items()}
tr, te = clean["train"], clean["test"]
assert pipeline._with_flags(clean, fin) == use
ref = tr[use].median()
train_raw = raw.loc[tr.index]
est = b["model"]
print(f"안정 변수 계산 ({b['chosen']} 시드 5개)…", flush=True)
allow = explain.stable_features(lambda random_state: model.candidate(b["chosen"], random_state=random_state, **cfg),
                                tr[use], tr["y"], top=len(use))
print("안정 변수:", allow, flush=True)

v1 = pd.read_csv(config.DATA / "processed" / "dataset.csv", dtype={"corp_code": str}, usecols=["corp_code", "bsns_year", "정정본재무"])
later_fix = set(zip(v1.loc[v1["정정본재무"] == 1, "corp_code"], v1.loc[v1["정정본재무"] == 1, "bsns_year"]))
ev = pd.read_csv(config.PROCESSED / "events.csv", dtype={"corp_code": str}, parse_dates=["event_date"])
from hup import dart                                       # noqa: E402  (캐시만 읽는다)
first = dart.first_filings()

# 사건 목록(회생 공시)을 마지막으로 수집한 날. 예측 기간이 이 날 뒤에 끝나면 결과 관측이 끝나지 않았다 (docs/15 §6-1)
EVENT_CUTOFF = pd.Timestamp("2026-09-04")
RATIOS = ["ROA", "영업이익률", "부채비율", "유동비율", "이자보상배율", "자본잠식률", "영업현금흐름_매출", "총자산회전율"]
# 위험 요인별로 사업보고서에서 더 확인할 곳 — 모델이 보지 않은 정보다
CHECK = {
    "자본잠식률": "자본변동표 · 감사보고서의 계속기업 관련 문단", "자본잠식": "자본변동표 · 감사보고서의 계속기업 관련 문단",
    "완전자본잠식": "감사보고서의 계속기업 관련 문단 · 자본 확충 계획", "자기자본비율": "자본변동표 · 차입금 현황",
    "부채비율": "차입금 만기 구조 (주석)", "유동비율": "단기차입금 · 유동성 위험 (주석)", "이자보상배율": "차입금 · 금융원가 내역 (주석)",
    "ROA": "사업의 내용 · 영업실적", "총자산영업이익률": "사업의 내용 · 영업실적", "영업이익률": "부문별 영업실적",
    "순이익률": "영업외손익 · 손상차손 (주석)", "영업현금흐름_매출": "현금흐름표 · 매출채권 회수", "영업현금흐름_부채": "현금흐름표",
    "총자산회전율": "자산 구성 · 매출 추이", "매출채권회전율": "매출채권 연령 · 대손충당금 (주석)", "재고자산회전율": "재고자산 평가 (주석)",
    "로그자산": "사업의 내용 (규모)", "영업손실": "부문별 영업실적", "2년연속영업손실": "부문별 영업실적 · 관리종목 지정 사유",
}


def sector(code):
    try:
        k = int(str(code)[:2])
    except ValueError:
        return "기타"
    for lo, hi, name in ((10, 34, "제조업"), (58, 63, "정보통신업"), (45, 47, "도소매업"), (41, 42, "건설업"),
                         (70, 73, "전문·과학·기술"), (49, 52, "운수·창고"), (86, 87, "보건·복지"), (35, 39, "전기·수도·환경")):
        if lo <= k <= hi:
            return name
    return "기타"


def fmt(name, v):
    unit = explain.PHRASE.get(name, ("", "", ""))[2]
    return explain.format_value(name, v, unit).strip(" ()").replace("실측 ", "")


def pct_rank(name, v):
    col = train_raw[name].dropna() if name in train_raw else pd.Series(dtype=float)
    if v is None or pd.isna(v) or col.empty:
        return None
    return round(float((col < v).mean() * 100), 1)


def factor(row, name, contrib):
    v = row.get(name)
    return {"var": name, "text": explain.sentence(name, v, ref, contrib), "value": "" if name in explain.FLAGS else fmt(name, v),
            "shap": round(float(contrib), 4), "pct": pct_rank(name, v), "risky_high": name in explain.HIGH_IS_RISKY,
            "median": fmt(name, ref.get(name)) if name in ref else "", "check": CHECK.get(name, "")}


def build(mask, group):
    part = te[mask]
    X = part[use]
    score = pd.Series(est.predict_proba(X)[:, 1], index=part.index)
    order = score.sort_values(ascending=False)
    rank_of = lambda v: int((order.to_numpy() > v).sum()) + 1
    top = order.index[: int(len(order) * 0.10)]
    sv = pd.DataFrame(explain.shap_values(est, X.loc[top]), index=top, columns=use)
    out = []
    for r_i, ix in enumerate(top, 1):
        row, v = raw.loc[ix], sv.loc[ix]
        wiped = explain._equity_wiped(row)
        why = explain.hold_reasons(row, v.to_numpy(), use, allow, ref)
        shown = explain._shown(v, allow, wiped)
        up = shown[shown > 0].sort_values(ascending=False).head(4)
        down = shown[shown < -1e-3].sort_values().head(2)      # 기여가 0 에 가까운 항목은 '낮춘 요인'으로 싣지 않는다
        fixed = [{"var": n, "old": explain.PHRASE[n][0], "new": explain.ABS_CUT[n][1]}
                 for n in up.index if explain._risky_side(n, row.get(n), ref) and explain.overstated(n, row.get(n))]
        cf = []
        if not why:
            _, items = explain.counterfactual(est, X.loc[ix], use, list(up.index), ref, min_drop=0.0,
                                              skip=explain.EQUITY_BASED if wiped else ())
            cf = [{"phrase": ph, "rank_from": r_i, "rank_to": rank_of(p)} for _n, _b, p, _t, ph in items
                  if rank_of(p) > r_i]
        T = row["rcept_dt"]
        topabs = v.abs().sort_values(ascending=False).index[:6]
        notes = []
        imputed = [n.removesuffix("_결측") for n in topabs if pd.isna(row.get(n.removesuffix("_결측")))]
        if imputed:
            notes.append(f"공시 값이 없어 대치값으로 판단한 변수: {', '.join(dict.fromkeys(imputed))}")
        if row.get("재무제표기준") == "OFS":
            notes.append("연결재무제표가 없어 별도재무제표 기준입니다")
        if (row["corp_code"], int(row["bsns_year"])) in later_fix:
            notes.append("이 사업보고서에는 나중에 정정 공시가 있었습니다 — 여기 값은 최초 공시 기준입니다")
        if row.get("제출기한연장") == 1:
            notes.append("이 사업보고서는 제출기한 연장 신고 후 제출됐습니다")
        if row.get("감사의견판정") not in (None, "적정") and pd.notna(row.get("감사의견판정")):
            notes.append(f"기준 보고서의 감사의견: {row.get('감사의견판정')}")
        e = ev[(ev.corp_code == row["corp_code"]) & (ev.event_date > T) & (ev.event_date <= T + pd.Timedelta(config.HORIZON_DAYS, "D"))]
        end = T + pd.Timedelta(config.HORIZON_DAYS, "D")
        outcome = {"y": int(row["y"]), "observed": bool(end <= EVENT_CUTOFF)}
        if len(e):
            e0 = e.sort_values("event_date").iloc[0]
            outcome.update(type=e0["event_type"], days=int((e0["event_date"] - T).days))
        checks_ = list(dict.fromkeys(f["check"] for f in [factor(row, n, c) for n, c in up.items()] if f["check"]))
        out.append({
            "_key": (row["corp_code"], int(row["bsns_year"])),
            "fy": int(row["bsns_year"]), "sector": sector(row.get("induty_code")), "group": group,
            "filed": T.strftime("%Y년 %m월"), "window_end": (T + pd.Timedelta(config.HORIZON_DAYS, "D")).strftime("%Y년 %m월"),
            "basis": "연결" if row.get("재무제표기준") == "CFS" else "별도",
            "rank": r_i, "n_group": len(order), "rank_pct": round(100 * r_i / len(order), 1),
            "alert": bool(score[ix] >= sel["경보 임계값 (검증 첫 부실, 정밀도 30% 이상인 가장 낮은 점수)"]),
            "status": "보류" if why else ("교정" if fixed else "통과"), "hold": why, "wiped": bool(wiped), "fixed": fixed,
            "up": [factor(row, n, c) for n, c in up.items()] if not why else [],
            "down": [factor(row, n, c) for n, c in down.items()] if not why else [],
            "top_model": [{"var": n, "shap": round(float(v[n]), 4)} for n in topabs[:5]],
            "ratios": [{"var": n, "value": fmt(n, row.get(n)), "median": fmt(n, ref.get(n)), "pct": pct_rank(n, row.get(n)),
                        "risky_high": n in explain.HIGH_IS_RISKY} for n in RATIOS],
            "notes": notes, "checks": checks_ or ["사업의 내용 · 감사보고서"], "cf": cf, "outcome": outcome,
        })
    return out


cards = build((te["과거사건"] == 0).to_numpy(), "첫 부실 대상") + build((te["과거사건"] == 1).to_numpy(), "부실 이력 있음")
random.Random(20261101).shuffle(cards)
for i, c in enumerate(cards, 1):
    c["id"] = f"{i:03d}"
# 시연 세 사례: 첫 부실 대상에서 ① 통과 ② 교정 ③ 보류 — 실제 사건이 있었던 기업을 먼저
demo = {}
# (시연 사례는 실제 사건이 있었던 기업을 먼저 골랐다 — 화면에 그렇게 밝힌다)
for c in sorted([c for c in cards if c["group"] == "첫 부실 대상"], key=lambda c: (-c["outcome"]["y"], c["rank"])):
    demo.setdefault(c["status"], c["id"])
names = pipeline.load()[["corp_code", "bsns_year", "corp_name"]].set_index(["corp_code", "bsns_year"])["corp_name"]

# ---- 공개판 익명화 (docs/15 §10) — 정확한 재무비율·표본 내 위치·순위·공시 월·사건 유형과 시점이 DART 대조로 기업을 특정하게 했다.
# 공개판에는 구간만, 정확한 값은 로컬 전용 파일에만.
EDGES = [(10, "하위 10% 이내", 5), (25, "하위 10~25%", 17.5), (50, "하위 25~50%", 37.5), (75, "상위 25~50%", 62.5),
         (90, "상위 10~25%", 82.5), (100.1, "상위 10% 이내", 95)]


def bucket(p):
    return (None, None) if p is None else next((lab, mid) for e, lab, mid in EDGES if p < e)


def rank_band(rank, n):
    q = 100 * rank / n
    return "상위 1% 이내" if q <= 1 else "상위 1~3%" if q <= 3 else "상위 3~5%" if q <= 5 else "상위 5~10%" if q <= 10 else "상위 10% 밖"


local = {}
for c in cards:
    ex = {"corp_code": c["_key"][0], "bsns_year": c["_key"][1], "name": names.get(c["_key"], ""), "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={first[c['_key']][0]}",
          "filed": c["filed"], "window_end": c["window_end"], "rank": c["rank"], "rank_pct": c["rank_pct"],
          "values": {}, "pct": {}, "cf": c["cf"], "outcome": c["outcome"]}
    for f in c["up"] + c["down"] + c["ratios"]:
        ex["values"][f["var"]], ex["pct"][f["var"]] = f["value"], f["pct"]
        lab, mid = bucket(f["pct"])
        f["value"], f["pct"] = lab or "", mid
        if "shap" in f:
            f["shap"] = round(f["shap"], 2)
    c["filed"] = c["filed"][:5]                                   # 'YYYY년'
    c["window_end"] = None
    c["rank_band"] = rank_band(c["rank"], c["n_group"])
    c["cf"] = [{"phrase": r["phrase"], "band_from": c["rank_band"], "band_to": rank_band(r["rank_to"], c["n_group"])} for r in c["cf"]]
    c["outcome"] = {"y": c["outcome"]["y"], "observed": c["outcome"]["observed"]}
    c["top_model"] = [{"var": m["var"], "shap": round(m["shap"], 2)} for m in c["top_model"]]
    for k in ("rank", "rank_pct", "_key"):
        del c[k]
    local[c["id"]] = ex
cards.sort(key=lambda c: (c["group"], ["상위 1% 이내", "상위 1~3%", "상위 3~5%", "상위 5~10%", "상위 10% 밖"].index(c["rank_band"]), c["id"]))
fr = ev_res["결과"]["관측 기간 내 첫 부실 (주 분석)"]
meta = {"판": config.VERSION, "모델": f"{b['chosen']} ({', '.join(f'{k} {v}' for k, v in cfg.items())}) — 검증 구간에서 사전 규칙으로 선택",
        "구간": "평가 구간 T 2024~2025 (v2.1 수정 후 재평가를 마친 구간 — 독립 검증 아님)", "선정": "집단별 위험 상위 10%",
        "데이터": "최초 공시 원본 XBRL 재무 (기준시점에 실제로 공개된 값)", "카드수": len(cards),
        "성능": {"첫부실_PR_AUC": round(fr["PR-AUC"], 3), "CI": fr["PR-AUC_95CI"], "기준선배": round(fr["PR-AUC"] / fr["기준선"], 1),
                 "경보": fr["경보 (검증에서 정한 임계값 그대로)"]},
        "demo": {"통과": demo.get("통과"), "교정": demo.get("교정"), "보류": demo.get("보류")}}
d = config.ROOT / "site" / "data"
d.mkdir(parents=True, exist_ok=True)
(d / "cards_v2.js").write_text("window.HUP_DATA = " + json.dumps({"meta": meta, "cards": cards}, ensure_ascii=False,
                                                                 default=lambda o: None) + ";\n")
(d / "local_names.js").write_text("window.HUP_LOCAL = " + json.dumps(local, ensure_ascii=False) + ";\n")
print(meta["demo"], pd.Series([c["status"] for c in cards]).value_counts().to_dict(),
      pd.Series([c["group"] for c in cards]).value_counts().to_dict())
