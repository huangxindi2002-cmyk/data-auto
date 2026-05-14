#!/bin/bash
# watch_and_resume.sh — 每 60 分钟探测一次 data.ai API
# 命中 200 → 立即 nohup 启动 run.py 并退出探测循环
# 命中 429 → 继续等待下一轮
#
# 用法（推荐通过 update.sh 调用）:
#   bash watch_and_resume.sh --month 2025-07 --tiktok 175.887 --kwai 68.967
#
# 也支持旧的环境变量方式:
#   MONTH=2025-07 TIKTOK=175.887 KWAI=68.967 bash watch_and_resume.sh

set -u
cd "$(dirname "$0")"

# 默认值（如果没传参，使用上次的输入）
LAST_INPUTS="$(pwd)/.last_inputs.json"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
ENV_FILE="$(pwd)/.env"
LOG="$(pwd)/watch_resume.log"

# 解析参数
MONTH="${MONTH:-}"
TIKTOK="${TIKTOK:-}"
KWAI="${KWAI:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --month)  MONTH="$2";  shift 2 ;;
    --tiktok) TIKTOK="$2"; shift 2 ;;
    --kwai)   KWAI="$2";   shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# 兜底：从 .last_inputs.json 读取
if [ -z "$MONTH" ] && [ -f "$LAST_INPUTS" ]; then
  MONTH=$($PYTHON -c "import json; print(json.load(open('$LAST_INPUTS')).get('month',''))" 2>/dev/null || echo "")
fi
if [ -z "$TIKTOK" ] && [ -f "$LAST_INPUTS" ]; then
  TIKTOK=$($PYTHON -c "import json; print(json.load(open('$LAST_INPUTS')).get('tiktok',''))" 2>/dev/null || echo "")
fi
if [ -z "$KWAI" ] && [ -f "$LAST_INPUTS" ]; then
  KWAI=$($PYTHON -c "import json; print(json.load(open('$LAST_INPUTS')).get('kwai',''))" 2>/dev/null || echo "")
fi

if [ -z "$MONTH" ] || [ -z "$TIKTOK" ] || [ -z "$KWAI" ]; then
  echo "[$(date)] ERROR: 缺少 month/tiktok/kwai 参数" | tee -a "$LOG"
  echo "用法: bash $0 --month YYYY-MM --tiktok 175.887 --kwai 68.967" | tee -a "$LOG"
  exit 1
fi

RUN_LOG="$(pwd)/run_${MONTH}.log"

# API KEY
if [ -f "$ENV_FILE" ]; then
  export $(grep -E '^DATAAI_API_KEY=' "$ENV_FILE" | head -1)
fi
if [ -z "${DATAAI_API_KEY:-}" ]; then
  echo "[$(date)] ERROR: DATAAI_API_KEY 未设置" | tee -a "$LOG"
  exit 1
fi

PROBE_URL="https://api.data.ai/v1.3/apps/google-play/app/20600000013820/details"

echo "[$(date)] watch_and_resume.sh 启动" | tee -a "$LOG"
echo "[$(date)]   month=$MONTH  tiktok=$TIKTOK  kwai=$KWAI" | tee -a "$LOG"
echo "[$(date)]   每 60 分钟探测一次 $PROBE_URL" | tee -a "$LOG"

ATTEMPT=0
while true; do
  ATTEMPT=$((ATTEMPT + 1))
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 \
    "$PROBE_URL" \
    -H "Authorization: Bearer $DATAAI_API_KEY" 2>/dev/null)

  echo "[$(date)] Probe #$ATTEMPT → HTTP $HTTP_CODE" | tee -a "$LOG"

  if [ "$HTTP_CODE" = "200" ]; then
    echo "[$(date)] ✅ API 已恢复，启动 run.py..." | tee -a "$LOG"
    nohup "$PYTHON" -u "$(pwd)/run.py" \
      --month "$MONTH" --tiktok "$TIKTOK" --kwai "$KWAI" \
      >> "$RUN_LOG" 2>&1 &
    BG_PID=$!
    echo "[$(date)] run.py 启动 PID=$BG_PID 日志=$RUN_LOG" | tee -a "$LOG"
    echo "[$(date)] watch_and_resume.sh 退出" | tee -a "$LOG"
    exit 0
  elif [ "$HTTP_CODE" = "429" ]; then
    echo "[$(date)] 仍在限流 (429)，60 分钟后再试" | tee -a "$LOG"
  elif [ "$HTTP_CODE" = "000" ]; then
    echo "[$(date)] 网络错误，60 分钟后再试" | tee -a "$LOG"
  else
    echo "[$(date)] 意外 HTTP $HTTP_CODE，60 分钟后再试" | tee -a "$LOG"
  fi
  sleep 3600
done
