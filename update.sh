#!/bin/bash
# update.sh — data-auto 一站式入口
# 用法: bash ~/data-auto/update.sh
set -u
cd "$(dirname "$0")"

PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
LAST_INPUTS="$(pwd)/.last_inputs.json"
ENV_FILE="$(pwd)/.env"

# 读取 API KEY
if [ -f "$ENV_FILE" ]; then
  export $(grep -E '^DATAAI_API_KEY=' "$ENV_FILE" | head -1)
fi

# 读取上次输入做默认值
LAST_MONTH=""
LAST_TIKTOK=""
LAST_KWAI=""
LAST_CSV_DIR=""
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

# 月份
read -p "月份 [$DEFAULT_MONTH]: " MONTH
MONTH=${MONTH:-$DEFAULT_MONTH}

# TikTok / Kwai
TT_PROMPT=${LAST_TIKTOK:-"竞对监控修正值"}
read -p "TikTok 修正时长 (十亿分钟) [$TT_PROMPT]: " TIKTOK
TIKTOK=${TIKTOK:-$LAST_TIKTOK}

KW_PROMPT=${LAST_KWAI:-"内部看板修正值"}
read -p "Kwai 修正时长 (十亿分钟) [$KW_PROMPT]: " KWAI
KWAI=${KWAI:-$LAST_KWAI}

# 数据源
echo ""
echo "数据源:"
echo "  [1] data.ai API 自动拉数（推荐）"
echo "  [2] 本地 CSV 文件夹（已手动下载）"
echo "  [3] 已有缓存 (raw_cache_${MONTH}.json)"
read -p "选择 [1]: " SOURCE
SOURCE=${SOURCE:-1}

CSV_DIR=""
case "$SOURCE" in
  2)
    DEFAULT_CSV_DIR=${LAST_CSV_DIR:-$HOME/Desktop/data.ai_${MONTH/-/}}
    read -p "CSV 文件夹路径 [$DEFAULT_CSV_DIR]: " CSV_DIR
    CSV_DIR=${CSV_DIR:-$DEFAULT_CSV_DIR}
    if [ ! -d "$CSV_DIR" ]; then
      echo "❌ 文件夹不存在: $CSV_DIR"
      exit 1
    fi
    ;;
esac

# 保存默认值
$PYTHON -c "
import json
d = {'month': '$MONTH', 'tiktok': '$TIKTOK', 'kwai': '$KWAI'}
if '$CSV_DIR': d['csv_dir'] = '$CSV_DIR'
json.dump(d, open('$LAST_INPUTS','w'), ensure_ascii=False, indent=2)
"

echo ""
echo "  月份:    $MONTH"
echo "  TikTok:  $TIKTOK"
echo "  Kwai:    $KWAI"
[ -n "$CSV_DIR" ] && echo "  CSV:     $CSV_DIR"
echo ""

# 跑 run.py
ARGS=(--month "$MONTH" --tiktok "$TIKTOK" --kwai "$KWAI")
case "$SOURCE" in
  2) ARGS+=(--csv-dir "$CSV_DIR") ;;
  3) ARGS+=(--use-cache) ;;
esac

RUN_LOG="run_${MONTH}.log"
"$PYTHON" -u run.py "${ARGS[@]}" 2>&1 | tee "$RUN_LOG"
EXIT_CODE=${PIPESTATUS[0]}

if [ "$EXIT_CODE" = "0" ]; then
  echo ""
  echo "═══════════════════════════════════════════════════════"
  echo "  ✅ 完成"
  echo "  Excel: 巴西数据底稿_${MONTH}.xlsx"
  echo "  画图工具已自动打开（浏览器）"
  echo "═══════════════════════════════════════════════════════"
else
  echo ""
  echo "❌ 出错（退出码 $EXIT_CODE），日志: $RUN_LOG"
  exit "$EXIT_CODE"
fi
