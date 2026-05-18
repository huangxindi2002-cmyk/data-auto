# data-auto

巴西月度数据自动化 → Excel 底稿 + 矩阵树图。

---

## 🌐 推荐：网页一键启动（GitHub Pages + Actions）

**任何人** 打开网页 → 填月份/TT/Kwai → 点按钮 → 几分钟后拿到 Excel 和图。

👉 **第一次使用前必读：[SETUP.md](./SETUP.md)**（5 分钟配置）

配好后：
- 浏览器打开 `https://huangxindi2002-cmyk.github.io/data-auto/`
- 填表 → 触发 → 等 → 自动出图
- 历史数据可下载、可重新画图

---

## 💻 本地一键启动（可选）

```bash
bash ~/data-auto/update.sh
```

交互式询问：
- 月份（默认上月）
- TikTok 总时长（覆盖 data.ai 拉的值）
- Kwai 总时长（覆盖 data.ai 拉的值）
- 数据来源（API / 本地 CSV / 缓存）

完成后自动打开画图工具（本地 HTTP 服务）。

## 输出

| 产物 | 路径 |
|------|------|
| Excel 底稿 | `巴西数据底稿_YYYY-MM.xlsx`（同目录 + `docs/data/`） |
| 画图工具（本地） | `tools/treemap_v2.html` |
| 画图工具（线上） | `docs/treemap.html`（Pages 部署后通过 `?excel=` 自动加载） |

## 高级用法

### 单独跑完整流程
```bash
python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967
```

### 用缓存出 Excel（不发任何 API 请求）
```bash
python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967 --use-cache
```

### 用本地 CSV 出 Excel（API 限流时）
```bash
python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967 --csv-dir /path/to/csvs
```

### CI 模式（不开浏览器、不启 HTTP 服务）
```bash
python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967 \
  --out docs/data/巴西数据底稿_2025-07.xlsx --no-open --no-server
```

## 画图（treemap_v2.html）

`tools/treemap_v2.html` 和 `docs/treemap.html` 是同一个自包含 web 应用：

- 精确测字（`getComputedTextLength`）
- 智能标签：内置 → 缩字 → 浅色 pill 外溢，三级降级
- Header 双行错位 + 牵引线
- 大类按 Excel 顺序、按类别色显示
- 数值 < 2 自动隐藏（避免主图杂乱）
- 标签可点击/拖拽编辑（字号、隐藏）
- 副标题从 sheet 名自动读取（"2025_07" → "2025年7月"）
- 月总时长从 R2 自动求和
- 导出 SVG / PNG 2×
- **自动加载**：URL 加 `?excel=xxx.xlsx` 启动时直接加载

## 项目结构

```
data-auto/
├── .github/workflows/update.yml   # GitHub Actions：网页触发的执行体
├── scripts/build_index.py         # 扫描 docs/data/ 生成文件清单
├── docs/                          # GitHub Pages 静态根目录
│   ├── index.html                 #   网页 UI（触发表单 + 历史列表）
│   ├── treemap.html               #   画图工具（自动加载 ?excel=）
│   └── data/                      #   每月 Excel 沉淀 + index.json
├── update.sh                      # 本地交互入口
├── run.py                         # CLI 入口
├── fetch.py                       # API 拉数（device=android+ios, pid→name 缓存）
├── csv_loader.py                  # 本地 CSV 读取
├── pipeline.py                    # 分类 + Top5 + TT/Kwai 覆盖
├── export.py                      # 输出 .xlsx
├── config.py                      # API_KEY / 分类列表 / 合并组
├── manual_rules.json              # APP → 分类规则
├── tools/treemap_v2.html          # 本地画图工具
├── product_id_cache.json          # pid → name 缓存（CI 也会 commit）
├── raw_cache_YYYY-MM.json         # API 原始数据（gitignored）
└── SETUP.md                       # GitHub Pages + Actions 配置教程
```

## 数据流

```
        ┌─ 网页（docs/index.html）
        │      ↓ workflow_dispatch
        │  GitHub Actions
        │      ↓
data.ai ─┴─→ fetch.py ─→ pipeline.py ─→ export.py ─→ 巴西数据底稿_YYYY-MM.xlsx
               ↑                                              │
TikTok手输 ────┴───────── pipeline overrides                  ↓
Kwai手输   ───────────── pipeline overrides         docs/treemap.html
                                                   （treemap + ?excel=自动加载）
```

`--tiktok` / `--kwai` 在 pipeline 里覆盖对应 APP 时长（类合计自动重算）。
