# data-auto 项目交接 SOP

> 核查日期：2026-09-29
> GitHub：<https://github.com/huangxindi2002-cmyk/data-auto>
> GitHub Pages：<https://huangxindi2002-cmyk.github.io/data-auto/>
> 默认分支：`main`

## 0. 交接结论（先看这里）

这个项目用于生成巴西移动 App 月度时长底稿，并通过 GitHub Pages 提供历史 Excel 下载和 treemap 可视化。

当前仅保留一套正式入口：

| 用途 | 当前入口 | 数据口径 | 可视化 |
|---|---|---|---|
| 正式月度底稿 / GitHub Actions | `run_phone.py` | `android_phone + iphone`（phone-only / All Phones） | Excel 由 Pages 的 `docs/treemap.html` 打开 |

旧的 `run.py`、`update.sh`、`csv_loader.py`、`scripts/regen_all.sh` 及重复的 `tools/treemap_v2.html` 已在 2026-09-29 清理；清理前快照保存在仓库外备份中。

本次核查确认：

- GitHub Pages 正常可访问；本次发布后历史数据将更新到 `2026-07`。
- 2026-07 已用 `raw_cache_phone_2026-07.json` 和固化规则成功重算。
- 当前正式仓库以远端最新 `origin/main` 为基线整合，不再保留清理前的分叉工作区状态。
- 清理前的本地代码、规则、缓存和产物已完整备份到仓库外。

---

## 1. 项目做什么

### 1.1 输入

每月需要：

1. 月份：`YYYY-MM`。
2. TikTok 修正时长：单位为十亿分钟（bn min）。
3. Kwai 修正时长：单位为十亿分钟（bn min）。
4. data.ai API 数据，或已经落盘的月度缓存。
5. `manual_rules.json` 中的 App 分类、拆分、排除和月度修正规则。

### 1.2 输出

主产物是：

- 单月 Excel：`巴西数据底稿_YYYY-MM.xlsx`。
- 线上文件：`docs/data/巴西数据底稿_YYYY-MM.xlsx`。
- 历史索引：`docs/data/index.json`。
- treemap：`docs/treemap.html?excel=data/<文件名>`。
- GitHub Actions Artifact：保留 90 天。

本地还存在增速榜、合并底稿、赛道分析等支线产物，详见第 8 节；它们目前不是线上月度 workflow 的一部分。

---

## 2. 当前正式运行链路

```text
GitHub Pages 表单
  └─ 输入 month / TikTok / Kwai / PAT
      └─ 调用 GitHub workflow_dispatch
          └─ .github/workflows/update.yml
              ├─ 安装 requirements.txt
              ├─ 从 GitHub Secret 写入 DATAAI_API_KEY
              ├─ 检查 docs/data/locked_months.json
              │   ├─ 已锁定且 Excel 存在：保留历史 Excel
              │   └─ 未锁定：运行 run_phone.py --use-cache
              ├─ pipeline.py 分类、拆分、合并、Top 5
              ├─ export.py 生成 Excel
              ├─ scripts/build_index.py 更新历史索引
              ├─ commit/push 回 main
              └─ 上传 Actions Artifact
```

### 2.1 核心代码职责

| 文件 | 职责 |
|---|---|
| `.github/workflows/update.yml` | 线上月度任务编排，GitHub 当前版本还包含历史月份锁定逻辑 |
| `run_phone.py` | 当前正式单月入口；切换为 phone-only 数据集，执行 fetch → pipeline → export |
| `fetch_phone.py` | 定义 phone-only 数据集：Android `android_phone` + iOS `iphone` |
| `fetch.py` | 请求 data.ai ranking/details API、解析 App 名、维护 product ID 缓存 |
| `pipeline.py` | 分类、TT/Kwai 覆盖、Instagram 拆分、App 合并、Top 5、其他、未分类清单 |
| `manual_rules.json` | 业务分类与月度修正规则，是核心业务资产 |
| `product_id_cache.json` | `platform:product_id → App 名` 缓存，减少 details API 调用 |
| `export.py` | 写单月 Excel |
| `scripts/build_index.py` | 扫描 `docs/data` 并生成 Pages 历史列表 |
| `docs/index.html` | Pages 操作页，触发 Actions 并展示历史文件 |
| `docs/treemap.html` | 在线读取 Excel 并生成 treemap |

### 2.2 TT/Kwai 覆盖优先级

`pipeline.py` 中的优先级为：

```text
命令行 --tiktok / --kwai
  > manual_rules.json 的 tt_kwai_monthly[month]
  > manual_rules.json 的通用 tt_kwai
```

命令行参数单位是“十亿分钟”，`run_phone.py` 会乘以 `1e9` 后传入 pipeline。

---

## 3. 新电脑首次配置

### 3.1 克隆与创建环境

```bash
git clone https://github.com/huangxindi2002-cmyk/data-auto.git
cd data-auto

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

当前依赖：

- `requests`
- `openpyxl`
- `python-dotenv`

线上 GitHub Actions 使用 Python 3.11；本次本机核查使用 Python 3.14.3，也可正常运行。

### 3.2 配置密钥

复制环境变量模板：

```bash
cp .env.example .env
```

填写：

```dotenv
DATAAI_API_KEY=<data.ai API key>
```

本机当前 `.env` 还配置了 `SENSORTOWER_API_KEY`，供 DAU/增速相关支线使用，但 `.env.example` 尚未记录。交接支线功能时需要另行安全传递该 key，**不要把 `.env` 提交到 Git**。

### 3.3 基础自检

```bash
python3 --version
python3 -c "import requests, openpyxl, dotenv; print('dependencies ok')"
python3 -m compileall -q .
```

---

## 4. 每月标准操作 SOP（推荐：GitHub 网页）

### 4.1 运行前准备

1. 从业务数据源取得当月 TikTok 和 Kwai 修正值，确认单位为**十亿分钟**。
2. 确认 GitHub 仓库 `Settings → Secrets and variables → Actions` 中存在 `DATAAI_API_KEY`。
3. 确认操作者有仓库 Actions 权限。
4. 确认目标月份是否已在 `docs/data/locked_months.json` 锁定。
   - 锁定月份重复触发时不会重新拉数，而是保留已确认 Excel。
   - 如确需重算，应先走评审，再修改锁定列表。
5. 查看最近 Actions，确认没有其他 `update-data` 任务正在执行。

### 4.2 从 Pages 触发

1. 打开 <https://huangxindi2002-cmyk.github.io/data-auto/>。
2. 填写月份、TikTok、Kwai。
3. 填写有仓库权限的 GitHub PAT。
4. 点击“触发更新”。
5. 打开页面给出的 Actions 日志链接，等待任务成功。
6. 完成后刷新历史数据，下载 Excel，并点击“画图”检查 treemap。

> 安全建议：现有网页把 PAT 存在浏览器 `localStorage`。不要在公共电脑使用；交接后建议优先从 GitHub Actions 页面手动 `Run workflow`，或改造成不需要浏览器持久化 PAT 的触发方式。

### 4.3 从 GitHub Actions 页面触发（更推荐）

1. 打开仓库 `Actions`。
2. 选择“更新月度数据”。
3. 点击 `Run workflow`。
4. 分支选择 `main`。
5. 填入 `month`、`tiktok`、`kwai`、`country=BR`。
6. 等待任务完成并检查日志、commit、Artifact、Pages 历史列表。

### 4.4 成功验收标准

- Actions 结论为 `success`。
- `main` 新增或更新目标月份 commit。
- `docs/data/巴西数据底稿_YYYY-MM.xlsx` 存在。
- `docs/data/index.json` 包含目标月份。
- Artifact 可以下载并打开。
- Pages 历史列表出现目标月份。
- treemap 可以加载，月份、类目和总量显示正常。
- 日志中的未分类大额 App 已人工复核。

---

## 5. 本地运行 SOP

### 5.1 正式主入口：phone-only

有对应缓存时：

```bash
python3 run_phone.py \
  --month 2026-07 \
  --use-cache \
  --tiktok <TikTok十亿分钟> \
  --kwai <Kwai十亿分钟> \
  --out output/巴西数据底稿_2026-07.xlsx
```

本次已验证的只读缓存命令：

```bash
python3 run_phone.py \
  --month 2026-07 \
  --use-cache \
  --out /tmp/verify_2026-07.xlsx
```

验证结果：

- 约 1.1 秒完成。
- 工作表：`2026_07`。
- 尺寸：86 行 × 15 列。
- 总计：1574.53 bn min（使用当前本地规则与缓存，未传 CLI TT/Kwai）。

### 5.2 新月份从 API 拉取

```bash
python3 run_phone.py \
  --month YYYY-MM \
  --tiktok <TikTok十亿分钟> \
  --kwai <Kwai十亿分钟> \
  --out output/巴西数据底稿_YYYY-MM.xlsx
```

会执行：

1. ranking API 拉取 8 组数据。
2. 对新 product ID 调 details API 补 App 名称。
3. 保存 `raw_cache_phone_YYYY-MM.json`。
4. 执行分类规则并导出 Excel。

### 5.3 `--use-cache` 的重要陷阱

`run_phone.py --use-cache` **不是严格离线模式**：

- 如果 `raw_cache_phone_YYYY-MM.json` 存在，就读缓存。
- 如果缓存不存在，脚本仍会回退到 data.ai API。

因此要保证不访问 API，运行前必须先检查：

```bash
test -f raw_cache_phone_YYYY-MM.json \
  && echo "cache exists" \
  || echo "STOP: cache missing; command will call API"
```

### 5.4 查看 Excel / treemap

`run_phone.py` 不会自动打开浏览器。可以把 Excel 放到 `docs/data/`，更新索引后启动静态服务：

```bash
cp output/巴西数据底稿_YYYY-MM.xlsx docs/data/
python3 scripts/build_index.py
python3 -m http.server 8000 --directory docs
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

停止服务：`Ctrl+C`。

### 5.5 已淘汰的旧口径

旧的含平板与本地 CSV 链路已经从正式仓库删除：

- `run.py`
- `update.sh`
- `csv_loader.py`
- `scripts/regen_all.sh`
- `tools/treemap_v2.html`（与 `docs/treemap.html` 完全重复）

不要再使用 `raw_cache_YYYY-MM.json` 生成或覆盖线上历史底稿。正式流程只使用 `run_phone.py` 与 `raw_cache_phone_YYYY-MM.json`。

---

## 6. 缓存、规则与数据口径

### 6.1 三类关键缓存

| 文件 | 内容 | 当前 Git 策略 |
|---|---|---|
| `product_id_cache.json` | product ID 到 App 名映射 | 已跟踪，线上会更新 |
| `raw_cache_phone_YYYY-MM.json` | phone-only 月度时长原始数据 | 本地多数被忽略；GitHub 当前对部分月份强制提交 |
| `raw_dau_cache_phone_YYYY-MM.json` | phone-only DAU 数据 | 本地存在，主要用于增速支线，当前未完整交接到远端 |

### 6.2 分类规则

`manual_rules.json` 决定：

- App → 中文类目。
- 排除项。
- TikTok/Kwai 月度值。
- Instagram 等 App 的拆分规则。
- 其他人工校正。

修改规则后必须至少：

1. 用一个历史月份缓存回算。
2. 对比总量、类目总量、Top 5 和未分类项。
3. 确认历史月份是否允许被重算。
4. 再提交规则变更。

### 6.3 当前类目

当前 `config.py` 定义 14 类：

`社交、泛短视频、直播、中长视频、短剧、社区、新闻资讯、在线阅读、浏览器/搜索、音乐/音频、游戏、电商、生活服务、AI`。

旧 `HANDOFF.md` 写的是 12 类，已经过时。

---

## 7. 故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `API_KEY 未设置` | `.env` / GitHub Secret 缺失 | 配置 `DATAAI_API_KEY`，不要提交明文 |
| HTTP 429 / quota exhausted | data.ai 分钟或日配额耗尽 | 保留已写缓存，稍后重试；不要删除 `product_id_cache.json` |
| `--use-cache` 却发起 API 请求 | 对应 phone cache 不存在 | 先用 `test -f` 检查缓存 |
| 输出总量与历史不一致 | phone-only 与含平板口径混用，或规则变化 | 核对入口、cache 前缀和 `manual_rules.json` 版本 |
| Pages 没有新月份 | workflow 未 push、index 未更新或 Pages 尚未部署 | 查 Actions 日志、`docs/data/index.json` 和 Pages workflow |
| Pages 显示旧列表 | CDN/浏览器缓存 | 等待部署完成后强刷；当前远端网页已有轮询刷新修复 |
| 历史月份被意外覆盖 | 未使用锁定列表或在旧本地分支执行 | 以 `origin/main` 的 `locked_months.json` 和 workflow 为准 |
| 旧口径文件被重新引入 | 从历史备份恢复了已淘汰入口 | 正式入口只允许 `run_phone.py`；不要恢复 `run.py/update.sh` |
| 大量未分类 App | 新 App 未进入人工规则或 API 名称变化 | 复核日志并更新 `manual_rules.json` |
| Actions push 冲突 | workflow 执行期间 `main` 有新提交 | 等任务结束后再推送；必要时重新运行 |

---

## 8. 已归档的本地分析支线

以下非正式功能没有进入当前 GitHub 主项目，已随清理前快照归档在仓库外备份中：

- `growth/` 增速榜模块
- `gen_growth_phone.py`
- `export_combined.py`
- `gen_rank_html.py`
- `gen_track_analysis.py`
- `fetch_dau_phone.py`
- 对应的 DAU 缓存、临时产物和桌面模板

它们不属于当前线上月度 workflow，也不作为本次项目交接的承诺功能。如未来恢复，应单独建分支、参数化本机路径并补充测试后再合并。

---

## 9. 2026-09-29 清理与整合记录

本次以 `origin/main` 为基线完成了本地最新规则整合：

- 保留远端 2026-05/06 数据、Pages 刷新修复和历史锁定机制。
- 合并本地新增的 11 条短剧 App 分类规则。
- 固化 2026-07 TikTok、Kwai 和 Instagram Reels 修正值。
- 合并 `product_id_cache.json`：保留远端已有映射并加入本地新增映射。
- 加入 `raw_cache_phone_2026-07.json` 和按最新规则重算的 2026-07 Excel。
- 将 2026-07 加入 `docs/data/locked_months.json`。
- 删除旧的含平板/本地 CSV 链路及重复 treemap 文件。
- 非正式增速和 DAU 分析支线只保留在仓库外备份，不进入正式仓库。

清理前完整备份：

```text
/Users/cccindy79/data-auto-handoff-backup-20260929-172257
```

备份包含完整 Git bundle、工作区 patch、未跟踪/忽略文件归档和单独受限权限保存的 `.env`。该路径属于原机器本地备份，不应提交到 GitHub。

### 2026-07 可复现基准

```text
TikTok             200.656 bn min
Kwai                61.246 bn min
Instagram Reels    136.317 bn min
社交类合计          405.90 bn min
泛短视频类合计      400.66 bn min
短剧类合计           12.24 bn min
全部类目合计       1591.57 bn min
```

---

## 10. 后续 Git 维护 SOP

### 10.1 每次修改前

```bash
git fetch origin --prune
git status --short --branch
```

工作区不干净时先提交到功能分支，不要直接覆盖或清理。

### 10.2 规则修改

1. 修改 `manual_rules.json`。
2. 使用对应月份的 `raw_cache_phone_YYYY-MM.json` 回算。
3. 对比总量、类目、Top 5 和未分类项。
4. 更新或确认 `docs/data/locked_months.json`。
5. 提交规则、原始缓存、Excel 和 `docs/data/index.json`。

### 10.3 发布前验收

```bash
python3 -m pip install -r requirements.txt
python3 -m compileall -q .
python3 run_phone.py --month 2026-07 --use-cache --out /tmp/handoff-check.xlsx
python3 scripts/build_index.py
```

再检查：

- 已锁定历史文件未被意外覆盖。
- Pages 和 workflow 文件语法正常。
- 新产物可打开且关键数值符合当月基准。
- `.env`、PAT、API key 未进入 Git。

### 10.4 权限与账号移交

当前仓库 owner 是 `huangxindi2002-cmyk`，本次提供的接手用户名是 `huangxindi03`。需明确采用哪种方式：

1. 将 `huangxindi03` 添加为 collaborator，并授予维护/写权限；或
2. 直接转移仓库 ownership；或
3. 由接手人 fork 后独立维护。

同时移交/重建：

- GitHub Actions Secret：`DATAAI_API_KEY`。
- Pages 配置：`main` + `/docs`。
- Branch protection / Actions 写权限。
- PAT：应由接手人自己创建，不要转交你的个人 PAT。
- data.ai / Sensor Tower 账号权限和配额说明。

若仓库 owner 改变，还要修改 `docs/index.html` 中的 `REPO_OWNER`，并更新 Pages URL 和文档链接。

---

## 11. 最终交接验收清单

### 代码与数据

- [ ] 本地所有变更已提交、归档或明确舍弃。
- [ ] 本地与远端分叉已解决。
- [ ] `manual_rules.json` 已由业务负责人确认。
- [ ] `product_id_cache.json` 已正确合并。
- [ ] 必要的 2026-07 及历史 cache 已安全交接。
- [ ] `.env` 和 token 未进入 Git。

### 运行

- [ ] 接手人在新环境成功安装依赖。
- [ ] 接手人用已有 cache 成功生成一次 Excel。
- [ ] 接手人成功触发一次 GitHub Actions。
- [ ] Pages 能看到目标月份并下载 Excel。
- [ ] treemap 能正常打开和导出。
- [ ] 未分类 App 和类目总量完成抽查。

### 权限

- [ ] 接手 GitHub 用户已获得仓库权限。
- [ ] Actions Secret 已重新配置或确认可用。
- [ ] Pages 配置已确认。
- [ ] 接手人拥有 data.ai 权限。
- [ ] 如交接增速支线，接手人拥有 Sensor Tower 权限。
- [ ] 原操作者的 PAT 已撤销或不再被共享使用。

---

## 12. 维护建议

1. 保持 `run_phone.py` 为唯一正式入口，禁止重新引入含平板的旧链路。
2. 给 `run_phone.py --use-cache` 增加“缓存不存在就报错”的严格离线模式，避免误触 API。
3. 去除分析脚本中的本机绝对路径。
4. 给 `requirements.txt` 固定版本，减少未来环境漂移。
5. 增加自动测试，至少覆盖分类、TT/Kwai 覆盖、App split/merge、历史锁定和 Excel 结构。
6. 不建议继续让用户在 Pages 的 `localStorage` 保存经典 PAT；优先使用 GitHub Actions 原生手动触发。
7. 每月发布前记录输入值、cache 来源、规则 commit SHA 和结果 commit SHA，形成可审计台账。
