#!/usr/bin/env bash
# 全量回算 13 个月（基于 raw_cache_*.json）
# 用法: bash scripts/regen_all.sh
set -euo pipefail

cd "$(dirname "$0")/.."

MONTHS=(
  2025-04 2025-05 2025-06 2025-07 2025-08 2025-09
  2025-10 2025-11 2025-12 2026-01 2026-02 2026-03 2026-04
)

mkdir -p docs/data

for m in "${MONTHS[@]}"; do
  echo ""
  echo "════════════════════════════════════════════════════════"
  echo " Regenerating $m"
  echo "════════════════════════════════════════════════════════"
  python3 run.py --month "$m" --use-cache --no-open --no-server \
    --out "docs/data/巴西数据底稿_${m}.xlsx"
done

echo ""
echo "✓ All 13 months regenerated under docs/data/"
