# data-auto

巴西月度数据自动化 → Excel 底稿 + 矩阵树图。

## 一键启动

```bash
bash ~/data-auto/update.sh
```

会交互式询问：
- 月份（默认上月）
- TikTok 总时长（从竞对监控页面取，覆盖 data.ai 拉的值）
- Kwai 总时长（从内部看板取，覆盖 data.ai 拉的值）

然后：
- ✅ API 可用 → 立即跑完整流程
- ⚠️ 429 → 询问是否启动后台监控（每 60 分钟探测，恢复后自动续传）
- 完成后自动打开画图工具

## 输出

| 产物 | 路径 |
|------|------|
| Excel 底稿 | `巴西数据底稿_YYYY-MM.xlsx`（同目录） |
| 画图工具 | `tools/treemap_v2.html`（自动在浏览器打开，上传 Excel 即可出图） |

## 高级用法

### 单独跑完整流程
```bash
python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967
```

### 配额耗尽时用缓存出 Excel（不发任何 API 请求）
```bash
python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967 --use-cache
```
- 当前缓存 9495/9495 (100%)，主要分类偏差 <5%
- 适用场景：上月跑完后想立即重新出图

### 手动启动后台监控
```bash
nohup bash watch_and_resume.sh --month 2025-07 --tiktok 175.887 --kwai 68.967 > watch.log 2>&1 &
tail -f watch.log
```
- 每 60 分钟 curl details 端点
- 命中 200 → 自动 nohup 启动 run.py
- 消耗 24 calls/day = <0.5% 日配额

### 手动检查 API 状态
```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 30 \
  "https://api.data.ai/v1.3/apps/google-play/app/20600000013820/details" \
  -H "Authorization: Bearer $(grep DATAAI_API_KEY ~/data-auto/.env | cut -d= -f2)"
# 200=可用  429=限流
```

## 画图（treemap_v2.html）

`tools/treemap_v2.html` 是一个自包含的单文件 web 应用，特性：

- 精确测字（`getComputedTextLength`）
- 智能标签：内置 → 缩字 → 浅色 pill 外溢，三级降级
- Header 双行错位 + 牵引线
- 大类按 Excel 顺序、按类别色显示
- 数值 < 2 自动隐藏（避免主图杂乱）
- 标签可点击/拖拽编辑（字号、隐藏）
- 副标题从 sheet 名自动读取（"2025_07" → "2025年7月"）
- 月总时长从 R2 自动求和
- 导出 SVG / PNG 2×

## 项目结构

```
data-auto/
├── update.sh            # 主入口（推荐用这个）
├── run.py               # CLI 入口（程序化用）
├── fetch.py             # Phase 1+2+3 数据拉取（含 fetch_from_cache）
├── pipeline.py          # 分类 + Top5 + 数据覆盖逻辑
├── export.py            # 输出 .xlsx
├── config.py            # API_KEY / 分类 / DISPLAY_OVERRIDES
├── classification_rules.json  # 258 条 app→分类 规则
├── watch_and_resume.sh  # API 恢复探测 + 自动续传
├── tools/
│   └── treemap_v2.html  # 画图工具（浏览器打开，上传 Excel）
├── product_id_cache.json     # 名称缓存（gitignored）
└── raw_cache_YYYY-MM.json    # Phase 1 原始数据（gitignored）
```

## 测试
```bash
python3 test_pipeline.py && python3 test_fetch.py
```

## 数据流

```
data.ai API ─┐
             ├─ run.py ─→ pipeline ─→ export.py ─→ 巴西数据底稿_YYYY-MM.xlsx
             │             ↑                              │
TikTok手输   ─┴─→ overrides                                │
Kwai手输    ─────→ overrides                               │
                                                          ↓
                                            tools/treemap_v2.html ─→ 画图（SVG/PNG）
```

`--tiktok` / `--kwai` 在 pipeline 里替换对应 APP 时长（方案 b：覆盖 APP 值，类合计自动重算）。
