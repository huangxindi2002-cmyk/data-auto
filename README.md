# data-auto

巴西移动 App 月度时长自动化：使用 data.ai **phone-only / All Phones** 口径生成 Excel 底稿，并通过 GitHub Pages 查看历史数据与 treemap。

- GitHub Pages：<https://huangxindi2002-cmyk.github.io/data-auto/>
- 完整交接与排障说明：[HANDOFF.md](./HANDOFF.md)
- 首次配置：[SETUP.md](./SETUP.md)

## 当前唯一正式入口

```bash
python3 run_phone.py \
  --month 2026-07 \
  --use-cache \
  --out output/巴西数据底稿_2026-07.xlsx
```

当前正式口径：

- Android：`android_phone`
- iOS：`iphone`
- 国家：`BR`
- 分类与业务修正：`manual_rules.json`

`run.py`、`update.sh`、`csv_loader.py` 和旧 `raw_cache_YYYY-MM.json` 含平板口径已经淘汰，不再使用。

## 本地安装

```bash
git clone https://github.com/huangxindi2002-cmyk/data-auto.git
cd data-auto
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中填写：

```dotenv
DATAAI_API_KEY=<your-data-ai-api-key>
```

不要提交 `.env`。

## 每月运行

### 使用已提交缓存

```bash
python3 run_phone.py \
  --month YYYY-MM \
  --use-cache \
  --out output/巴西数据底稿_YYYY-MM.xlsx
```

`--use-cache` 只有在 `raw_cache_phone_YYYY-MM.json` 存在时才真正离线；缓存缺失时脚本会调用 API。运行前可检查：

```bash
test -f raw_cache_phone_YYYY-MM.json
```

### 从 API 拉取新月份

```bash
python3 run_phone.py \
  --month YYYY-MM \
  --tiktok <TikTok十亿分钟> \
  --kwai <Kwai十亿分钟> \
  --out output/巴西数据底稿_YYYY-MM.xlsx
```

### 2026-07 可复现基准

2026-07 的业务修正已固化在 `manual_rules.json`：

- TikTok：`200.656` 十亿分钟
- Kwai：`61.246` 十亿分钟
- Instagram Reels：`136.317` 十亿分钟

因此可直接执行：

```bash
python3 run_phone.py \
  --month 2026-07 \
  --use-cache \
  --out output/巴西数据底稿_2026-07.xlsx
```

## 线上流程

```text
GitHub Pages / GitHub Actions
  → .github/workflows/update.yml
  → run_phone.py
  → fetch.py
  → pipeline.py
  → export.py
  → docs/data/巴西数据底稿_YYYY-MM.xlsx
  → scripts/build_index.py
  → GitHub Pages
```

已确认的历史月份记录在 `docs/data/locked_months.json`，重复触发时不会覆盖已有 Excel。

## 输出

| 产物 | 路径 |
|---|---|
| 月度 Excel | `docs/data/巴西数据底稿_YYYY-MM.xlsx` |
| phone-only 原始缓存 | `raw_cache_phone_YYYY-MM.json` |
| 历史索引 | `docs/data/index.json` |
| 在线 treemap | `docs/treemap.html` |

本地查看 Pages：

```bash
python3 -m http.server 8000 --directory docs
```

然后访问 <http://127.0.0.1:8000/>。

## 核心文件

```text
.github/workflows/update.yml   GitHub Actions 月度任务
run_phone.py                   正式 CLI 入口
fetch_phone.py                 phone-only 数据集定义
fetch.py                       data.ai API 与名称缓存
pipeline.py                    分类、修正、拆分、合并、Top 5
manual_rules.json              业务规则与月度修正
product_id_cache.json          product ID → App 名缓存
export.py                      Excel 导出
docs/index.html                Pages 操作页
docs/treemap.html              treemap 页面
docs/data/locked_months.json   已确认历史月份锁定列表
scripts/build_index.py         Pages 历史文件索引
```

## 发布前检查

```bash
python3 -m compileall -q .
python3 run_phone.py --month 2026-07 --use-cache --out /tmp/data-auto-check.xlsx
python3 scripts/build_index.py
```

更多 Git 清理、权限移交、缓存管理和故障排查见 `HANDOFF.md`。
