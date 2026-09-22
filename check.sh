#!/bin/zsh
# 코드를 고쳤으면 이걸 돌린다. 개별 테스트만 돌리다 다른 하나가 깨진 걸
# 늦게 발견한 적이 있다(2026-09-05, test_pipeline).
set -e
cd "$(dirname "$0")"
echo "── ruff"
uvx ruff check src tests --select F,E9 --output-format concise
echo "── 테스트 개수 (줄어들면 실패)"
# 2026-09-22: 문자열 구간 치환으로 회귀 테스트 5개를 통째로 날렸다.
# 사이에 있던 함수들이 함께 지워졌는데 남은 테스트는 전부 통과해서 눈치채지 못했다.
N=$(grep -c "^def test_" tests/test_smoke.py)
MIN=16
[ "$N" -ge "$MIN" ] || { echo "테스트가 $N 개다 (최소 $MIN). 지워진 것이 없는지 확인할 것"; exit 1; }
echo "$N 개 (최소 $MIN)"

echo "── test_smoke (규칙 점검)"
.venv/bin/python -W error::DeprecationWarning tests/test_smoke.py
echo "── test_pipeline (합성 데이터 전 구간)"
.venv/bin/python -W error::DeprecationWarning tests/test_pipeline.py > /dev/null && echo "전 구간 통과"
echo "── 전부 통과"
# 주의: ./check.sh | tail 로 돌리면 파이프 종료코드가 tail 것이라 실패가 묻힌다.
# 그냥 ./check.sh 로 돌리거나, 꼭 파이프를 쓰면 `set -o pipefail` 을 켤 것.
