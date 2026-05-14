# data-auto Project Handoff

> 用户：巴西移动应用市场数据分析师
> 目标：把每月手动从 data.ai 下 CSV → 拼 Excel 底稿的工作流，替换成 API 自动化脚本
> **死线：本周五（2026-05-15）交付完整的「拉取 + 更新 + 画图」脚本**
> 项目位置：`~/data-auto/`
> GitHub：`github.com/huangxindi2002-cmyk/data-auto`（main 分支）

---

## 1. 架构

```
~/data-auto/
├── fetch.py          # data.ai API 三阶段抓取
├── pipeline.py       # 12 类分类合计 + Top5 + others
├── export.py         # 输出 .xlsx
├── run.py            # CLI 入口
├── config.py         # API_KEY、CATEGORIES_ZH、DISPLAY_OVERRIDES、CSV_APP_TIME_CATS
├── classification_rules.json   # 258 条业务规则（app name → 中文分类）
├── test_pipeline.py  # 7 个单测（已通过）
├── test_fetch.py     # 5 个单测（已通过，含 429 边界）
├── product_id_cache.json       # 名称缓存（gitignored）
└── raw_cache_2025-07.json      # Phase 1 落盘（gitignored）
```

**12 个中文分类**（`config.CATEGORIES_ZH`）：
社交、泛短视频、直播、长视频、社区、新闻资讯、在线阅读、浏览器/搜索、音乐/音频、游戏、电商、生活服务

**口径区分**（关键业务逻辑）：
- **Overall 口径**：长视频/泛短视频/直播/社区/新闻资讯/浏览器/搜索/生活服务 → cat_total 用统一时长
- **CSV 口径**（`config.CSV_APP_TIME_CATS`）：游戏、电商、在线阅读、音乐/音频 → cat_total 用 Application Time
- **社交特殊**：cat_total 用 Overall，但 Top5 排序按 csv_times

---

## 2. data.ai API 官方规则（已确认）

来源：`helpcenter.data.ai/community/s/article/5-Rate-Limits`（需登录）

| 维度 | 规则 | 我们的影响 |
|-----|------|----------|
| **基础 RPM** | 500 requests/min **per contract** | 我们 ~17 RPM，远低于 |
| **重接口 RPM** | 部分 endpoint 仅 30 RPM（列表不完整公开）| `app/{pid}/details` 是否在内？官方未列出，但建议 ≤25 RPM 保守 |
| **日配额** | 默认值因合同而异，**官方未公开统一数字**；本合同当前 **5000/天** | 单日跑不完首次冷启动 |
| **重置时间** | **官方未公开** | 必须探测式恢复 |
| **upscale** | 联系 CSM 调整 default daily/per-min | 短期联系不到 |

**已知低速率接口（30 RPM）部分清单**：GameIQ Taxonomy Apps v1.3、Store Stats Ratings History v1.2/1.3、AppRatingsV12/V13、DailyFeaturesV12/V13、FeatureHistoryV12

**Endpoint 我们用的**：
- `GET /v1.3/intelligence/apps/{market}/usage-ranking`（Phase 1，16 calls/month）
- `GET /v1.3/apps/{market}/app/{pid}/details`（Phase 2，每个 unique product_id 一次）

---

## 3. 关键设计决策（重要！）

### 3.1 Phase 2 缓存策略 — 这是性能 & 配额平衡的核心
- product_id → unified_product_name 是**永久不变**的映射
- 首次跑：解析所有 unique IDs（约 **9495 个**）
- 后续每月：**只解析新进 TOP 1000 的 ~50-200 个 APP**，其余命中缓存
- 缓存文件每 50 个 ID 落盘一次（`product_id_cache.json`），支持断点续传

### 3.2 Phase 1 raw cache — Phase 1 数值每月必跑
- usage-ranking 的 `total_minutes` 每月不同（动态）
- 但 product_id 列表月度高度重叠
- `raw_cache_{month}.json` 让 Phase 1 中断后能续传

### 3.3 429 处理（已通过踩坑修复）
- `_resolve_one` 重试 3 次失败 → **抛 `QuotaExhausted` 异常，不缓存 None**
- 旧版 bug：失败后缓存 None，恢复时被永久跳过 → 数据丢失
- 现在：异常向上传播，`run.py` 顶层捕获，友好退出 + sys.exit(2)
- 单测覆盖：`test_fetch.py::test_three_429s_raise_quota_exhausted`

### 3.4 others 计算口径一致性
- CSV 口径分类：`others = cat_total - sum(csv_times[name] for top5)`，**不能用 display_time**（DISPLAY_OVERRIDES 可能污染）
- 单测覆盖：`test_pipeline.py::test_csv_kou_jing_others_fix`

---

## 4. 实测的"反直觉"事实

| 反直觉 | 真实情况 |
|--------|---------|
| 1s/call sleep ≈ 1s/call 总耗时 | **错**。网络 RTT 2-4s，总 = sleep + RTT ≈ 5s/call |
| TOP 1000 × 16 datasets 去重后 ~3000-5000 个 ID | **错**。实测 **9495 个**唯一 ID |
| 首次跑 2-3 小时 | **错**。9495 × 5s = **~13 小时**（理论），实际因配额 = 2 天 |
| 日配额耗尽时 retry-after=60 有用 | **错**。`retry-after` 头始终 60s 但 daily limit error 时 60s 完全不够 |
| UTC 00:00 是重置时间 | **错**。官方未公开重置时间 |

---

## 5. 当前状态（截至 2026-05-14 11:30）

- **缓存**：`product_id_cache.json` 含 7000/9495（73.7%）。剩 2495 个等 API 恢复。
- **Phase 1**：完整。`raw_cache_2025-07.json` 16 datasets 全有。
- **配额**：5016/5000（已超），API 正在 lock-out
- **GitHub**：commit `cedca27` 已推。本地无未推送修改。
- **launchd**：已自卸载（08:00 触发时撞配额，正确触发 QuotaExhausted 退出）

---

## 6. 还没做的（Friday 死线前必须）

### 必做 #1：`--use-cache` fallback 模式
**为什么**：API 不知何时恢复，必须能用**现有 7000 cached** 跑出 Excel。
**实现**：在 `run.py` 加 `--use-cache` 选项，跳过 Phase 1 + Phase 2（直接走缓存）。`_build_datasets` 现在已经能容忍缺失 IDs（找不到名字就跳过该条记录），所以 pipeline 本身可以工作。
**预期输出**：丢失 26% 低排名 APP，主要分类合计偏差通常 <5%（高排名 APP 全在缓存里）。

### 必做 #2：画图模块（**完全没动**）
- 选项 A：复用 `~/Desktop/treemap-app/treemap.html`（已有的矩阵树图）→ 写胶水把 pipeline 输出塞进去
- 选项 B：Python matplotlib/plotly 新写
- 用户尚未明确指定形式。建议先按 A 走，因为已有美术资产

### 必做 #3：自动探测+续传脚本（防御性，不影响交付）
**为什么**：万一 API 在死线前恢复，自动跑完全量数据。
**实现**：bash 脚本每 60 min curl 1 次 details 端点，命中 200 立刻 nohup 启动 `run.py`。每次探测吃 1 个配额，60 min 间隔 = 24 calls/day = <0.5% 配额，可接受。

### 可选：fetch.py 加显式 RPM 限流
**风险**：当前 2s/call ≈ 30 RPM 正好踩重接口红线。若 data.ai 把 details 移进 30 RPM 桶，会一直 429。
**建议**：token bucket 限到 25 RPM 更稳健。但当前 2s 已经足够慢，可以推迟。

---

## 7. 快速参考

### 跑数命令
```bash
cd ~/data-auto && python3 -u run.py --month 2025-07 --tiktok 175.887 --kwai 68.967
```
TikTok/Kwai 数值每月从用户的竞对监控/内部看板手动取。

### 验证基准（2025-07）— `run.py::SMOKE_TARGETS`
```
社交: 408.53      泛短视频: 509.50    直播: 1.878
长视频: 270.94    社区: 19.12         新闻资讯: 0.750
在线阅读: 8.97    浏览器/搜索: 91.36  音乐/音频: 23.16
游戏: 151.14      电商: 30.34         生活服务: 7.74
```
单位十亿分钟。脚本会自动对比 ±0.5 容差。

### 测试命令
```bash
cd ~/data-auto && python3 test_pipeline.py && python3 test_fetch.py
```

### 检查 API 是否恢复
```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 30 \
  "https://api.data.ai/v1.3/apps/google-play/app/20600000013820/details" \
  -H "Authorization: Bearer $(grep DATAAI_API_KEY ~/data-auto/.env | cut -d= -f2)"
# 200 = 恢复；429 = 仍限速
```
注意：每次探测吃 1 个配额。

---

## 8. 用户偏好（来自记忆系统）

- 沟通风格：**简洁直接**，不要长篇解释
- 直接动手，少铺垫
- 喜欢量化对比（速率、ETA、ROI 表格）
- 中文优先

---

## 9. 给接手 agent 的优先级建议

1. **先问用户**：画图选 A 还是 B（决定下一小时投入方向）
2. **并行实现** `--use-cache` 模式 + 画图脚本 + 自动探测
3. **死线日**（5/15）：交付 `脚本（完整功能）+ 部分数据 Excel + 图`
4. **下个月开始**：缓存温热后，每月运行成本是 5-15 分钟，问题彻底消失
