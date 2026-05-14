# data-auto 使用手册

## 快速命令

### 正常月度跑数（API 配额充足时）
```bash
cd ~/data-auto
python3 -u run.py --month 2025-07 --tiktok 175.887 --kwai 68.967
```

### 配额耗尽时用缓存出 Excel（当前场景）
```bash
cd ~/data-auto
python3 -u run.py --month 2025-07 --tiktok 175.887 --kwai 68.967 --use-cache
```
- 完全不发 API 请求
- 当前缓存 7000/9495 (73.7%)，主要分类偏差 <5%
- 输出：`巴西数据底稿_2025-07.xlsx`

---

## 画矩阵树图（treemap）

**前提**：已有 `巴西数据底稿_YYYY-MM.xlsx`

**步骤**：
1. 用浏览器打开 `~/Desktop/treemap-app/treemap.html`
   ```bash
   open ~/Desktop/treemap-app/treemap.html
   ```
2. 点击「**上传 Excel**」→ 选择 `巴西数据底稿_2025-07.xlsx`
3. 等 2-3 秒图自动渲染
4. 右侧可调：颜色、标签字号、大类间距、Top N 标签数量
5. 导出：
   - **导出 SVG**：矢量格式，可在 Illustrator/Figma 继续编辑
   - **导出 PNG 2×**：高清光栅，适合汇报 PPT

**Excel 格式说明**（treemap.html 期望）：
- Row 1：大类名（12 列 = 12 个分类）
- Row 2：各分类合计（十亿分钟）
- Row 3+：APP 名称 + 数值（稀疏格式，不同列）
- 最后一行：「其他」+ 各类 others 值

脚本生成的 `巴西数据底稿_YYYY-MM.xlsx` 已严格按此格式输出，**直接上传即可**。

---

## API 自动恢复监控

API 配额通常在北京时间某个时间点重置（官方未公开，实测约 08:00-12:00）。

### 启动探测脚本（后台运行）
```bash
nohup bash ~/data-auto/watch_and_resume.sh &
tail -f ~/data-auto/watch_resume.log
```
- 每 60 分钟 curl 一次 details 端点
- 命中 200 → 自动 `nohup python3 run.py ...` 启动完整流程
- 每次探测消耗 1 个配额，24 calls/day = <0.5% 日配额

### 手动检查 API 是否恢复
```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 30 \
  "https://api.data.ai/v1.3/apps/google-play/app/20600000013820/details" \
  -H "Authorization: Bearer $(grep DATAAI_API_KEY ~/data-auto/.env | cut -d= -f2)"
# 200 = 恢复；429 = 仍限速
```

---

## 验证基准（2025-07）

```
分类        目标(十亿分钟)  --use-cache实际  偏差
社交           408.53       380.68        -6.8%
泛短视频        509.50       495.75        -2.7%
直播             1.88         1.29        -31%（绝对值小，-0.6）
长视频          270.94       262.66        -3.1%
社区            19.12        16.74        -12%（绝对值小）
新闻资讯          0.75         0.42        ✓（差 <0.5）
在线阅读          8.97         7.04        -21%（绝对值小）
浏览器/搜索      91.36        91.18        ✓
音乐/音频        23.16        20.82        -10%（绝对值小）
游戏           151.14       113.41        -25%（低排名游戏多）
电商            30.34        29.97        ✓
生活服务          7.74         7.22        -6.7%
```

游戏偏差最大（-37），因为 TOP 1000 里大量低排名游戏 APP 集中在未缓存区。
API 恢复后跑完整流程，数值会对齐到目标值。

---

## 测试
```bash
cd ~/data-auto
python3 test_pipeline.py && python3 test_fetch.py
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `run.py` | CLI 入口（支持 `--use-cache`） |
| `fetch.py` | Phase 1+2+3 数据拉取；`fetch_from_cache()` 为缓存模式 |
| `pipeline.py` | 分类逻辑 + Top5 + others |
| `export.py` | 输出 .xlsx |
| `config.py` | API KEY、分类定义、DISPLAY_OVERRIDES |
| `classification_rules.json` | 258 条 app→分类 规则 |
| `watch_and_resume.sh` | API 恢复探测 + 自动续传 |
| `product_id_cache.json` | 名称缓存（7000/9495，gitignored） |
| `raw_cache_2025-07.json` | Phase 1 原始数据（gitignored） |
