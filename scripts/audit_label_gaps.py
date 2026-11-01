# 라벨 누락 점검 (2026-11-01): 예측 창 (T, T+400일] 안에 실제로 접수된 '최초' 사업보고서의 감사의견이 비적정인데 y=0 인 행.
# 결산월을 바꾼 기업은 한 사업연도에 보고서가 둘이거나(FY2025.09 + FY2025.12), 다음 보고서가 수집 범위 밖 사업연도(FY2026)일 수 있다.
# 실행: HUP_VERSION=v2 PYTHONPATH=src DART_API_KEY=... .venv/bin/python scripts/audit_label_gaps.py
import pandas as pd
from hup import config, dart, labels

assert config.VERSION.startswith("v2")
df = pd.read_csv(config.PROCESSED / "dataset.csv", dtype={"corp_code": str}, parse_dates=["rcept_dt"])
corps = set(df.corp_code)
reports = {}                      # corp → [(접수일, 접수번호, 사업연도)]  최초 공시만 (정정·첨부 제외)
for y in range(2015, 2027):
    for d in dart.disclosures_all(f"{y}0101", f"{y}1231", pblntf_detail_ty="A001"):
        m = dart._FY.search(d.get("report_nm", ""))
        if d["corp_code"] in corps and m and d["report_nm"].lstrip().startswith("사업보고서"):
            reports.setdefault(d["corp_code"], []).append((pd.Timestamp(d["rcept_dt"]), d["rcept_no"], int(m.group(1))))
h = pd.Timedelta(config.HORIZON_DAYS, "D")
rows, nomatch = [], []
for _, r in df.iterrows():
    for dt, no, fy in reports.get(r.corp_code, []):
        if r.rcept_dt < dt <= r.rcept_dt + h:
            resp = dart.audit_opinion(r.corp_code, fy)
            cur = [x for x in resp if x.get("rcept_no") == no and "당기" in (x.get("bsns_year") or "").replace(" ", "").replace("\n", "")]
            # 감사의견 응답의 접수번호는 최신 정정본이다. 그 사업연도 보고서가 하나뿐이면 당기 행이 곧 그 보고서의 의견이다
            n_reports = sum(1 for _, _, f in reports[r.corp_code] if f == fy)
            if not cur and n_reports == 1 and labels.current_period(resp):
                cur = [labels.current_period(resp)]
            op = (cur[0].get("adt_opinion") if cur else None) or ""
            if not cur:
                cur_all = [x for x in resp if "당기" in (x.get("bsns_year") or "").replace(" ", "").replace("\n", "")]
                adverse = any(labels.classify_opinion(x.get("adt_opinion")) == "비적정" for x in cur_all)
                nomatch.append((r.corp_code, r.bsns_year, no, "그 사업연도 응답에 비적정 있음" if adverse else "그 사업연도 응답 전부 비적정 아님", int(r.y)))
            if labels.classify_opinion(op) == "비적정":
                rows.append({"corp_code": r.corp_code, "bsns_year": r.bsns_year, "T": r.rcept_dt.date(), "보고서접수": dt.date(),
                             "보고서_사업연도": fy, "접수번호": no, "의견": op, "y": int(r.y)})
t = pd.DataFrame(rows)
miss = t[t["y"] == 0] if len(t) else t
print("창 안 최초 보고서의 비적정 의견:", len(t), "· 그중 라벨 y=0 (누락):", len(miss))
print(miss.to_string(index=False) if len(miss) else "누락 없음")
nm = pd.DataFrame(nomatch, columns=["corp_code", "bsns_year", "접수번호", "판정", "y"])
print("창 안 보고서 중 접수번호로 의견을 특정 못 한 것:", len(nm)); print(nm.groupby(["판정", "y"]).size().to_string())
print("API 호출", dart.CALLS)
