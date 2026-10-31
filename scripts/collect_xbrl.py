# 2차 연구 데이터: 최초 접수번호의 원본 XBRL 수집 (docs/15 §3).
# 실행: PYTHONPATH=src DART_API_KEY=... .venv/bin/python scripts/collect_xbrl.py <shard 0|1> <shards 2>
# 캐시(data/cache/xbrl)가 있어 몇 번이고 다시 돌려도 된다. 한도 초과면 0 으로 끝난다(내일 이어서).
import sys
import pandas as pd
from hup import config, dart, xbrl

shard, shards = int(sys.argv[1]), int(sys.argv[2])
ff = dart.first_filings()
keys = pd.read_csv(config.PROCESSED / "dataset.csv", dtype={"corp_code": str}, usecols=["corp_code", "bsns_year"])
todo = sorted({ff[(c, y)][0] for c, y in zip(keys.corp_code, keys.bsns_year)})[shard::shards]
done = none = 0
try:
    for i, rc in enumerate(todo, 1):
        if xbrl.fetch(rc) is None:
            none += 1
        done += 1
        if i % 500 == 0:
            print(f"[{shard}] {i}/{len(todo)} 원본없음 {none} 호출 {dart.CALLS}", flush=True)
except dart.QuotaExceeded as e:
    print(f"[{shard}] 한도 도달 {done}/{len(todo)} — {e}", flush=True)
    sys.exit(0)
print(f"[{shard}] 완료 {done}/{len(todo)} 원본없음 {none} 호출 {dart.CALLS}", flush=True)
