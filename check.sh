#!/bin/zsh
# 코드를 고쳤으면 이걸 돌린다. 개별 테스트만 돌리다 다른 하나가 깨진 걸
# 늦게 발견한 적이 있다(2026-09-05, test_pipeline).
set -e
cd "$(dirname "$0")"
echo "── ruff"
uvx ruff check src tests --select F,E9 --output-format concise
echo "── test_smoke (규칙 점검)"
.venv/bin/python -W error::DeprecationWarning tests/test_smoke.py
echo "── test_pipeline (합성 데이터 전 구간)"
.venv/bin/python -W error::DeprecationWarning tests/test_pipeline.py > /dev/null && echo "전 구간 통과"
echo "── 전부 통과"
