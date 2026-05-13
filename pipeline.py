"""
Classification and category totals.
Ported from data-updates/index.html (runPipeline + compute logic).

Input:  datasets dict from fetch.fetch_all(), tiktok_override, kwai_override
Output: {
  cat: {
    "total":  float billion_min,
    "top5":   [{"name": str, "display_time": float billion_min, "rank": int}, ...],
    "others": float billion_min,
  },
  ...
}
plus:
  "unknown":    [{"name": str, "time": float}, ...]
  "kwai_rank":  int
  "grand_total": float
"""

import json
import os
import config

_RULES_PATH = os.path.join(os.path.dirname(__file__), "classification_rules.json")

with open(_RULES_PATH, encoding="utf-8") as _f:
    RULES: dict[str, str] = json.load(_f)
# Merged WhatsApp is always Social regardless of JSON
RULES["WhatsApp Messenger & WhatsApp Business"] = "社交"

# Category CSV key → our Chinese category (only the ones that feed Application Time buckets)
_CSV_KEY_TO_ZH = {
    "social":   "社交",
    "books":    "在线阅读",
    "music":    "音乐/音频",
    "games":    "游戏",
    "shopping": "电商",
    "news":     "新闻资讯",
    # "video" intentionally omitted – 长视频 uses Overall口径
}


def _apply_overrides(overall, tiktok_bn, kwai_bn):
    for item in overall:
        if item["name"] == "TikTok" and tiktok_bn is not None:
            item["time"] = tiktok_bn
        elif item["name"] == "Kwai" and kwai_bn is not None:
            item["time"] = kwai_bn


def _merge_whatsapp(overall):
    wa_m = next((r for r in overall if r["name"] == "WhatsApp Messenger"), None)
    wa_b = next((r for r in overall if r["name"] == "WhatsApp Business"), None)
    if wa_m and wa_b:
        wa_m["name"] = "WhatsApp Messenger & WhatsApp Business"
        wa_m["time"] += wa_b["time"]
        return [r for r in overall if r["name"] != "WhatsApp Business"]
    if wa_m:
        wa_m["name"] = "WhatsApp Messenger & WhatsApp Business"
    return overall


def _build_cat_groups(overall, app_to_csv_cat):
    cat_groups = {c: [] for c in config.CATEGORIES_ZH}
    unknown = []
    for item in overall:
        rule = RULES.get(item["name"])
        if rule == "忽略":
            continue
        if rule and rule in cat_groups:
            cat_groups[rule].append(item)
        elif not rule:
            implied = app_to_csv_cat.get(item["name"])
            if implied and implied in cat_groups:
                cat_groups[implied].append(item)
            elif item["time"] > 1.0:
                unknown.append(item)
    return cat_groups, unknown


def _supplement_news(cat_groups, cat_csv_times, app_to_csv_cat):
    """Step 5.5 from index.html: add small news apps from News CSV."""
    news_csv = cat_csv_times.get("新闻资讯", {})
    if not news_csv:
        return
    existing = {i["name"] for i in cat_groups["新闻资讯"]}
    # (a) explicit news rules not in Overall CSV
    for name, cat in RULES.items():
        if cat != "新闻资讯" or name in existing:
            continue
        t = news_csv.get(name)
        if t:
            cat_groups["新闻资讯"].append({"name": name, "time": t, "rank": 999})
            existing.add(name)
    # (b) news CSV apps with no explicit rule, not claimed by another CSV
    for name, t in news_csv.items():
        if name in existing:
            continue
        rule = RULES.get(name)
        if rule == "忽略" or (rule and rule != "新闻资讯"):
            continue
        implied = app_to_csv_cat.get(name)
        if implied and implied != "新闻资讯":
            continue
        cat_groups["新闻资讯"].append({"name": name, "time": t, "rank": 999})


def _display_val(name, overall_bn):
    do = config.DISPLAY_OVERRIDES
    return do[name] / 1e9 if name in do else overall_bn


def _compute_category(cat, cat_groups, cat_csv_times):
    csv_times = cat_csv_times.get(cat, {})
    has_csv = bool(csv_times)
    DO = config.DISPLAY_OVERRIDES

    if cat in config.CSV_APP_TIME_CATS and has_csv:
        # Totals from Application Time; exclude apps explicitly cross-classified
        cat_total = sum(
            t for name, t in csv_times.items()
            if not (RULES.get(name) and RULES[name] != cat and RULES[name] in config.CATEGORIES_ZH)
        )
        eligible = [i for i in cat_groups[cat] if i["name"] in csv_times]
        eligible.sort(key=lambda i: DO.get(i["name"], i["time"] * 1e9), reverse=True)
        top_items = eligible[:5]
        top5 = [
            {
                "name": i["name"],
                "display_time": _display_val(i["name"], i["time"]),
                "rank": i["rank"],
            }
            for i in top_items
        ]
        # others 与 cat_total 同口径（Application Time），不能用可能被 DISPLAY_OVERRIDES 改过的 display_time
        others = max(0.0, cat_total - sum(csv_times.get(i["name"], 0.0) for i in top_items))

    elif cat == "社交" and has_csv:
        cat_total = sum(i["time"] for i in cat_groups[cat])
        sorted_items = sorted(
            cat_groups[cat],
            key=lambda i: csv_times.get(i["name"], i["time"]),
            reverse=True,
        )
        top_items = sorted_items[:5]
        top5 = [
            {
                "name": i["name"],
                "display_time": _display_val(i["name"], i["time"]),
                "rank": i["rank"],
            }
            for i in top_items
        ]
        others = max(0.0, cat_total - sum(i["time"] for i in top_items))

    else:
        # Overall口径: 长视频/泛短视频/直播/社区/新闻资讯/浏览器搜索/生活服务
        cat_total = sum(i["time"] for i in cat_groups[cat])
        sorted_items = sorted(
            cat_groups[cat],
            key=lambda i: DO.get(i["name"], i["time"] * 1e9),
            reverse=True,
        )
        top_items = sorted_items[:5]
        top5 = [
            {
                "name": i["name"],
                "display_time": _display_val(i["name"], i["time"]),
                "rank": i["rank"],
            }
            for i in top_items
        ]
        others = max(0.0, cat_total - sum(i["time"] for i in top_items))

    return {"total": cat_total, "top5": top5, "others": others}


def run(datasets, tiktok_bn=None, kwai_bn=None):
    """
    datasets: output of fetch.fetch_all()
    tiktok_bn / kwai_bn: manual override in billion minutes (float or None)

    Returns dict with category results + metadata.
    """
    overall = list(datasets["overall"])  # copy

    # Step 1-3: merge WhatsApp, apply overrides
    overall = _merge_whatsapp(overall)
    _apply_overrides(overall, tiktok_bn, kwai_bn)

    # Step 4: build cat_csv_times (Application Time buckets)
    cat_csv_times = {}
    app_to_csv_cat = {}
    for csv_key, zh_cat in _CSV_KEY_TO_ZH.items():
        data = datasets.get(csv_key, {})
        if not data:
            continue
        # Remove standalone WhatsApp records (already merged)
        data = {k: v for k, v in data.items()
                if k not in ("WhatsApp Messenger", "WhatsApp Business")}
        cat_csv_times[zh_cat] = data
        for name in data:
            if name not in app_to_csv_cat:
                app_to_csv_cat[name] = zh_cat

    # Step 5: classify
    cat_groups, unknown = _build_cat_groups(overall, app_to_csv_cat)

    # Step 5.5: news supplement
    _supplement_news(cat_groups, cat_csv_times, app_to_csv_cat)

    # Step 6: compute per-category results
    result = {}
    grand_total = 0.0
    for cat in config.CATEGORIES_ZH:
        result[cat] = _compute_category(cat, cat_groups, cat_csv_times)
        grand_total += result[cat]["total"]

    kwai_item = next((r for r in overall if r["name"] == "Kwai"), None)
    kwai_rank = kwai_item["rank"] if kwai_item else "—"

    # 校验 DISPLAY_OVERRIDES：列表里的 APP 必须在 overall 中出现，否则是静默失败（名称变更/拼写错误）
    overall_names = {r["name"] for r in overall}
    missing_overrides = [n for n in config.DISPLAY_OVERRIDES if n not in overall_names]
    if missing_overrides:
        print(f"\n  ⚠ DISPLAY_OVERRIDES 中以下 APP 未出现在 overall 数据中（覆盖值无效）:")
        for n in missing_overrides:
            print(f"      - {n}")

    return {
        "categories": result,
        "unknown": sorted(unknown, key=lambda i: i["time"], reverse=True),
        "grand_total": grand_total,
        "kwai_rank": kwai_rank,
        "missing_overrides": missing_overrides,
    }
