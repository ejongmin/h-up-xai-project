# 최초 공시 원문의 감사의견 수집 (docs/15 §11) — 감사의견 API 가 정정본 의견을 준 기업-연도만.
# 실행: HUP_VERSION=v2.1 PYTHONPATH=src DART_API_KEY=... .venv/bin/python scripts/collect_audit_original.py <shard> <shards>
import sys
import pandas as pd
from hup import config, dart, labels

shard, shards = int(sys.argv[1]), int(sys.argv[2])
ff = dart.first_filings()
d = pd.read_csv(config.PROCESSED / "dataset.csv", dtype={"corp_code": str}, usecols=["corp_code", "bsns_year"])
todo = []
for cc, fy in zip(d.corp_code, d.bsns_year):
    r = labels.current_period(dart.audit_opinion(cc, int(fy)))
    if r and r.get("rcept_no") != ff[(cc, int(fy))][0]:
        todo.append(ff[(cc, int(fy))][0])
todo = sorted(set(todo))[shard::shards]
try:
    for i, rc in enumerate(todo, 1):
        dart.audit_opinion_original(rc)
        if i % 250 == 0:
            print(f"[{shard}] {i}/{len(todo)} 호출 {dart.CALLS}", flush=True)
except dart.QuotaExceeded as e:
    print(f"[{shard}] 한도 도달 {i}/{len(todo)} — {e}", flush=True)
    sys.exit(0)
print(f"[{shard}] 완료 {len(todo)} 호출 {dart.CALLS}", flush=True)
