#!/bin/bash
# update.sh — data-auto 一站式入口
# 用法: bash ~/data-auto/update.sh
#
# 流程:
#   1. 询问月份 / TikTok / Kwai 时长（带上次默认值）
#   2. 探测 data.ai API
#      ├─ 200 → 立即跑 run.py
#      └─ 429 → 询问是否启动 watch_and_resume.sh 后台监控
#   3. 完成后自动打开 treemap_v2.html

set -u
cd "$(dirname "$0")"

PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
LAST_INPUTS="$(pwd)/.last_inputs.json"
ENV_FILE="$(pwd)/.env"
# RUN_LOG 在 MONTH 获取后设置，统一为 run_${MONTH}.log，与 watch_and_resume.sh / README 一致

# 读取 API KEY
if [ -f "$ENV_FILE" ]; then
  export $(grep -E '^DATAAI_API_KEY=' "$ENV_FILE" | head -1)
fi
if [ -z "${DATAAI_API_KEY:-}" ]; then
  echo "❌ 错误: DATAAI_API_KEY 未设置（请检查 .env）"
  exit 1
fi

# 读取上次输入做默认值
LAST_MONTH=""
LAST_TIKTOK=""
LAST_KWAI=""
if [ -f "$LAST_INPUTS" ]; then
  LAST_MONTH=$($PYTHON -c "import json; print(json.load(open('$LAST_INPUTS')).get('month',''))" 2>/dev/null || echo "")
  LAST_TIKTOK=$($PYTHON -c "import json; print(json.load(open('$LAST_INPUTS')).get('tiktok',''))" 2>/dev/null || echo "")
  LAST_KWAI=$($PYTHON -c "import json; print(json.load(open('$LAST_INPUTS')).get('kwai',''))" 2>/dev/null || echo "")
fi
DEFAULT_MONTH=${LAST_MONTH:-$(date -v-1m +%Y-%m)}

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  📊 data-auto · 巴西月度数据自动化"
echo "═══════════════════════════════════════════════════════"
echo ""

# 1. 月份
read -p "月份 [$DEFAULT_MONTH]: " MONTH
MONTH=${MONTH:-$DEFAULT_MONTH}

# 2. TikTok
DEFAULT_TIKTOK_PROMPT=${LAST_TIKTOK:-"竞对监控页面取数"}
read -p "TikTok 总时长 (十亿分钟) [$DEFAULT_TIKTOK_PROMPT]: " TIKTOK
TIKTOK=${TIKTOK:-$LAST_TIKTOK}

# 3. Kwai
DEFAULT_KWAI_PROMPT=${LAST_KWAI:-"内部看板取数"}
read -p "Kwai 总时长 (十亿分钟) [$DEFAULT_KWAI_PROMPT]: " KWAI
KWAI=${KWAI:-$LAST_KWAI}

if [ -z "$TIKTOK" ] || [ -z "$KWAI" ]; then
  echo "❌ TikTok 和 Kwai 时长必填"
  exit 1
fi

# 保存为下次默认值
$PYTHON -c "
import json
json.dump({'month': '$MONTH', 'tiktok': '$TIKTOK', 'kwai': '$KWAI'},
          open('$LAST_INPUTS', 'w'), indent=2, ensure_ascii=False)
"

echo ""
echo "  月份:    $MONTH"
echo "  TikTok:  $TIKTOK"
echo "  Kwai:    $KWAI"
echo ""

# 日志统一命名（与 watch_and_resume.sh / README 一致）
RUN_LOG="$(pwd)/run_${MONTH}.log"


# 4. 探测 API
echo "🔍 探测 data.ai API 状态..."
PROBE_URL="https://api.data.ai/v1.3/apps/google-play/app/20600000013820/details"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 \
  "$PROBE_URL" -H "Authorization: Bearer $DATAAI_API_KEY" 2>/dev/null)

case "$HTTP_CODE" in
  200)
    echo "✅ API 可用，立即启动完整流程"
    echo "   日志: $RUN_LOG"
    echo ""
    "$PYTHON" -u run.py --month "$MONTH" --tiktok "$TIKTOK" --kwai "$KWAI" 2>&1 | tee "$RUN_LOG"
    EXIT_CODE=${PIPESTATUS[0]}
    if [ "$EXIT_CODE" = "0" ]; then
      echo ""
      echo "✅ 完成！Excel: 巴西数据底稿_${MONTH}.xlsx"
      echo "🎨 打开画图工具..."
      open "$(pwd)/tools/treemap_v2.html"
    else
      echo ""
      echo "⚠️  run.py 退出码 $EXIT_CODE，可能是配额耗尽。"
      echo "    可使用 --use-cache 模式："
      echo "    $PYTHON run.py --month $MONTH --tiktok $TIKTOK --kwai $KWAI --use-cache"
    fi
    ;;

  429)
    echo "⚠️  API 限流 (429)，配额已耗尽"
    echo ""
    read -p "是否启动后台监控（每60分钟探测，恢复后自动续传）？[Y/n]: " ANSWER
    ANSWER=${ANSWER:-Y}
    if [[ "$ANSWER" =~ ^[Yy] ]]; then
      WATCH_LOG="$(pwd)/watch_resume.log"
      nohup bash "$(pwd)/watch_and_resume.sh" \
        --month "$MONTH" --tiktok "$TIKTOK" --kwai "$KWAI" \
        > "$WATCH_LOG" 2>&1 &
      WATCH_PID=$!
      echo "✅ 后台监控已启动 (PID $WATCH_PID)"
      echo "   监控日志: tail -f $WATCH_LOG"
      echo "   恢复后会自动跑 run.py 并写日志到 run_${MONTH}.log"
      echo ""
      read -p "现在用 --use-cache 出一个临时 Excel？[y/N]: " CACHE_ANS
      if [[ "$CACHE_ANS" =~ ^[Yy] ]]; then
        echo "🔄 用缓存生成临时 Excel..."
        "$PYTHON" -u run.py --month "$MONTH" --tiktok "$TIKTOK" --kwai "$KWAI" --use-cache 2>&1 | tee "$RUN_LOG"
        if [ -f "巴西数据底稿_${MONTH}.xlsx" ]; then
          echo "🎨 打开画图工具..."
          open "$(pwd)/tools/treemap_v2.html"
        fi
      fi
    else
      echo "已取消"
    fi
    ;;

  000)
    echo "❌ 网络错误（curl 超时/DNS 失败）"
    exit 1
    ;;

  *)
    echo "⚠️  API 返回 HTTP $HTTP_CODE"
    read -p "仍然尝试运行 run.py？[y/N]: " ANS
    if [[ "$ANS" =~ ^[Yy] ]]; then
      "$PYTHON" -u run.py --month "$MONTH" --tiktok "$TIKTOK" --kwai "$KWAI" 2>&1 | tee "$RUN_LOG"
    fi
    ;;
esac
