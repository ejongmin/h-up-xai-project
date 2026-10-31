# 2차에서 새로 채워진 값의 출처 검산 (docs/15 §3-4). 1차(API)에서 비었는데 2차(원본 XBRL)에서 채워진 행을 표본으로,
# 어떤 계정(코드/한글 라벨)에서 값을 가져왔는지, 1차 API 응답에는 그 계정이 어떤 이름으로 있었는지를 나란히 남긴다.
# 실행: PYTHONPATH=src .venv/bin/python scripts/audit_accounts.py  → results/v2/data_check/계정검산_*.csv
import collections
import pandas as pd
from hup import config, dart, features, xbrl

v1 = pd.read_csv(config.DATA / "processed" / "dataset.csv", dtype={"corp_code": str})
v2 = pd.read_csv(config.DATA / "processed_v2" / "dataset.csv", dtype={"corp_code": str})
m = v1.merge(v2, on=["corp_code", "bsns_year"], suffixes=("_1", "_2"))
ff = dart.first_filings()


def source(rows, key):
    """features.extract 와 같은 순서로 찾아, 값을 준 행의 (경로, 계정코드, 이름, 값)."""
    grp, ids, nms = features.ACCOUNTS[key]
    for sj in features.SJ[grp]:
        for aid in ids:
            for r in rows:
                if r["sj_div"] == sj and r["account_id"] == aid and r.get("thstrm_amount") not in (None, "", "-"):
                    return "코드", aid, r.get("account_nm", ""), r["thstrm_amount"]
        for nm in nms:
            for r in rows:
                if r["sj_div"] == sj and (r.get("account_nm") or "").replace(" ", "") == nm and r.get("thstrm_amount") not in (None, "", "-"):
                    return "이름", r["account_id"], r["account_nm"], r["thstrm_amount"]
    return None, None, None, None


def api_names(rows, words):
    return "; ".join(sorted({f"{r.get('account_id')}:{(r.get('account_nm') or '').replace(' ', '')}"
                             for r in rows if any(w in (r.get("account_nm") or "") for w in words)}))[:200]


plan = {"이자보상배율": ("interest_exp", ["이자", "금융원가", "금융비용"]),
        "자본잠식률": ("capital_stock", ["자본금"]),
        "매출채권회전율": ("receivable", ["매출채권"])}
for var, (acc, words) in plan.items():
    new = m[m[f"{var}_1"].isna() & m[f"{var}_2"].notna()]
    s = new.sample(min(40, len(new)), random_state=0)
    out, paths = [], collections.Counter()
    for _, r in s.iterrows():
        rows, _ = xbrl.pick(xbrl.parse(xbrl.fetch(ff[(r.corp_code, int(r.bsns_year))][0]), int(r.bsns_year))[0])
        how, aid, nm, val = source(rows, acc)
        api, _ = dart.financials(r.corp_code, int(r.bsns_year), fs_div=r["재무제표기준_1"])
        a1 = features.extract(api)
        paths[(how, aid if how == "코드" else nm)] += 1
        out.append({"corp_code": r.corp_code, "bsns_year": int(r.bsns_year), "2차_경로": how, "2차_계정코드": aid, "2차_라벨": nm,
                    "2차_값": val, "1차_해당계정값": a1[acc], "1차_영업이익": a1["op_income"],
                    "1차_비슷한계정": api_names(api, words), "1차_재무기준": r["재무제표기준_1"], "2차_재무기준": r["재무제표기준_2"]})
    d = config.ROOT / "results" / "v2" / "data_check"
    pd.DataFrame(out).to_csv(d / f"계정검산_{var}.csv", index=False, encoding="utf-8-sig")
    print(f"== {var}: 1차 결측·2차 값 {len(new)}행 중 {len(s)}행 표본")
    for k, v in paths.most_common():
        print("  ", v, k)
