"""KRX 일별 시세 수집. 종목당 1회, 캐시 후 재시작 시 건너뛴다."""
import sys, time
sys.path.insert(0, "src")
from hup import dart, market

uni = dart.universe()
tickers = {r["corp_code"]: r["stock_code"] for r in dart.corp_codes() if r.get("stock_code")}
todo = [(c, tickers[c]) for c in sorted(uni) if c in tickers]
print(f"대상 {len(todo)}종목", flush=True)
ok = skip = fail = 0
for i, (cc, t) in enumerate(todo):
    try:
        s = market.prices(t, "20140101", "20261231")
        ok += 1 if len(s) else 0
        skip += 0 if len(s) else 1
    except Exception as e:
        fail += 1
        if fail < 5: print(f"  실패 {t}: {type(e).__name__}", flush=True)
    if i % 200 == 0:
        print(f"  {i}/{len(todo)}  성공 {ok} 빈응답 {skip} 실패 {fail}", flush=True)
print(f"완료: 성공 {ok} / 빈응답 {skip} / 실패 {fail}", flush=True)
