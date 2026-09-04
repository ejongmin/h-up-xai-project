#!/bin/zsh
# 감시 루프. 어떤 이유로 죽든 60초 뒤 되살린다 — 캐시가 있어 재시작 비용은 0이다.
# 정상 종료(exit 0 = 일일 한도 도달 또는 수집 완료)면 루프를 끝낸다.
# 2026-09-03: DNS 단절이 파이썬 재시도(31초 백오프)를 넘겨서 프로세스가 전부 죽었다.
#             재시도 횟수를 늘리는 것보다 바깥에서 되살리는 쪽이 원인을 안 가린다.
cd "$(dirname "$0")"
set -a; . ./.env; set +a
SHARD=$1; KEY=$2
export PYTHONPATH=src DART_API_KEY=$KEY
n=0
until .venv/bin/python -m hup.cli fs "$SHARD"; do
  n=$((n+1))
  echo "[감시] 비정상 종료 ${n}회 — 60초 후 재시작 $(date '+%H:%M:%S')"
  sleep 60
done
echo "[감시] 정상 종료 (한도 도달 또는 완료) $(date '+%H:%M:%S')"
