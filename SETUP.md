# 🚀 一次性配置（5 分钟）

把这套流程接入 GitHub Pages，以后任何人打开网址 → 填月份/TT/Kwai → 点按钮 → 等几分钟就拿到 Excel 和图。

---

## Step 1️⃣  把 data.ai 的 API Key 存到 GitHub Secrets

1. 浏览器打开 https://github.com/huangxindi2002-cmyk/data-auto
2. 顶部 **Settings** → 左侧 **Secrets and variables** → **Actions**
3. 点 **New repository secret**
   - Name：`DATAAI_API_KEY`
   - Secret：粘贴你的 data.ai API Key（也就是本地 `.env` 里那串）
4. 点 **Add secret**

> 这是加密存储，不会出现在任何日志里。

---

## Step 2️⃣  开启 GitHub Pages

1. 同样在仓库 **Settings** → 左侧 **Pages**
2. **Source** 选 `Deploy from a branch`
3. **Branch** 选 `main`，文件夹选 `/docs`
4. 点 **Save**
5. 等 1–2 分钟，页面顶部会出现绿色提示 `Your site is live at https://huangxindi2002-cmyk.github.io/data-auto/`

把这个网址记下来，下面要用。

---

## Step 3️⃣  生成 Personal Access Token (PAT)

> 网页要通过 GitHub API 触发 Actions，必须用 PAT 鉴权。

1. 浏览器打开 https://github.com/settings/tokens
2. 右上 **Generate new token** → **Generate new token (classic)**
3. 填写：
   - **Note**：`data-auto`
   - **Expiration**：90 days（到期再生成一个就行）
   - **Scopes** 勾选：
     - ☑ `repo`（全部子项）
     - ☑ `workflow`
4. 拉到最下面 **Generate token**
5. 复制 `ghp_xxxxxxxxxxxx`（**只显示一次**，丢了只能重新生成）

---

## Step 4️⃣  打开网页开干

1. 浏览器打开 Step 2 那个 Pages 网址：`https://huangxindi2002-cmyk.github.io/data-auto/`
2. 填：
   - **月份**：例如 `2026-04`
   - **TikTok**：例如 `175.887`
   - **Kwai**：例如 `68.967`
   - **PAT**：粘贴 Step 3 的 `ghp_xxx`（只存在你浏览器 localStorage，不会上传到任何服务器）
3. 点 **触发更新**
4. 页面会显示实时状态：触发中 → Run 已开始 → 运行中 → ✅ 完成
5. 完成后下方 **历史数据** 会自动刷新出新月份，点 **🎨 画图** 直接看 treemap

---

## 🔧 给别人复用

任何人都可以用这套，只要：
- 你给他 **网址** + **PAT**（或者让他自己生成自己的 PAT，前提是他在协作者列表里）
- 不需要装 Python、不需要装任何东西，连终端都不用开

如果是想 fork 给完全独立的另一个团队，让他改 `docs/index.html` 顶部的：
```js
const REPO_OWNER = 'xxx';   // 改成自己的 GitHub 用户名
const REPO_NAME  = 'yyy';   // 改成自己的仓库名
```

---

## 🐛 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| 点按钮后弹 `Dispatch 失败 (401)` | PAT 错或过期 | 重新生成 PAT |
| 点按钮后弹 `Dispatch 失败 (404)` | 仓库名/workflow 名错 | 检查 `docs/index.html` 顶部配置 |
| Run 失败 / quota exhausted | API 配额耗尽（429） | 等次日重试，product_id_cache 已自动 commit，下次会快很多 |
| 历史数据列表显示 `index.json 不存在` | 还没跑过一次完整流程 | 先成功跑一次就有了 |
| 网址 404 | Pages 还没生效或路径错 | 等 2 分钟；检查 Settings → Pages 源是不是 `main` + `/docs` |

---

## 📁 仓库结构（CI 相关）

```
.github/workflows/update.yml   ← workflow_dispatch，可手动触发
scripts/build_index.py         ← 扫 docs/data/ 生成 index.json
docs/
  index.html                   ← Pages 首页：触发按钮 + 历史列表
  treemap.html                 ← treemap_v2 的副本，支持 ?excel=URL
  data/
    巴西数据底稿_YYYY-MM.xlsx   ← workflow 自动 commit
    index.json                  ← 文件清单，给前端读
```

工作流：
```
点按钮 → fetch GitHub API /actions/workflows/update.yml/dispatches
       → Actions runner 启动 → run.py 全流程 →
       → 生成 docs/data/巴西数据底稿_<月>.xlsx
       → scripts/build_index.py 更新 index.json
       → git push 回 main
       → GitHub Pages 自动重新部署（30 秒内）
       → 网页历史列表刷新看到新文件
```
