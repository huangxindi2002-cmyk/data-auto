#!/bin/bash
# watch_and_resume.sh — 每 60 分钟探测一次 data.ai API。
# 命中 200 → 立即 nohup 启动完整 run.py 并退出探测循环。
# 命中 429  → 继续等待下一轮。
# 用法:
#   nohup bash ~/data-auto/watch_and_resume.sh &
#   tail -f ~/data-auto/watch_resume.log
#
# 每次探测消耗 1 个配额；60 min 间隔 = 24 calls/day = <0.5% 日配额，可接受。

set -u
cd "$(dirname "$0")"

LOG="$(pwd)/watch_resume.log"
RUN_LOG="$(pwd)/run_2025-07.log"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
ENV_FILE="$(pwd)/.env"

# 读取 API KEY
if [ -f "$ENV_FILE" ]; then
  export $(grep -E '^DATAAI_API_KEY=' "$ENV_FILE" | head -1)
fi

if [ -z "${DATAAI_API_KEY:-}" ]; then
  echo "[$(date)] ERROR: DATAAI_API_KEY not set. Exiting." | tee -a "$LOG"
  exit 1
fi

# 探测端点（一个已知 product_id）
PROBE_URL="https://api.data.ai/v1.3/apps/google-play/app/20600000013820/details"
MONTH="2025-07"
TIKTOK="175.887"
KWAI="68.967"

echo "[$(date)] watch_and_resume.sh started. Will probe every 60 min." | tee -a "$LOG"
echo "[$(date)] Probe URL: $PROBE_URL" | tee -a "$LOG"

ATTEMPT=0
while true; do
  ATTEMPT=$((ATTEMPT + 1))
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 \
    "$PROBE_URL" \
    -H "Authorization: Bearer $DATAAI_API_KEY" 2>/dev/null)

  echo "[$(date)] Probe #$ATTEMPT → HTTP $HTTP_CODE" | tee -a "$LOG"

  if [ "$HTTP_CODE" = "200" ]; then
    echo "[$(date)] API RECOVERED (200)! Launching run.py in background..." | tee -a "$LOG"
    nohup "$PYTHON" -u "$(pwd)/run.py" \
      --month "$MONTH" \
      --tiktok "$TIKTOK" \
      --kwai "$KWAI" \
      >> "$RUN_LOG" 2>&1 &
    BG_PID=$!
    echo "[$(date)] run.py started with PID $BG_PID. Log: $RUN_LOG" | tee -a "$LOG"
    echo "[$(date)] watch_and_resume.sh exiting (job handed off)." | tee -a "$LOG"
    exit 0

  elif [ "$HTTP_CODE" = "429" ]; then
    echo "[$(date)] Still rate-limited (429). Next probe in 60 min." | tee -a "$LOG"

  elif [ "$HTTP_CODE" = "000" ]; then
    echo "[$(date)] Network error (curl timeout/DNS). Next probe in 60 min." | tee -a "$LOG"

  else
    echo "[$(date)] Unexpected HTTP $HTTP_CODE. Next probe in 60 min." | tee -a "$LOG"
  fi

  sleep 3600
done
