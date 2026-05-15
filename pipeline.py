"""
pipeline_v2.py — 与 cross_check Excel 算法 100% 对齐

输入: csv_data dict[csv_cat_eng, list[{name, time(min)}]]
    必须包含 'Overall' + 7 个分类 CSV (Social/Photo & Video/Music/News & Magazines/
    Books & Reference/Games/Shopping)

算法（完全复刻 cross_check Excel 的 4 个 sheet）:

1. 「统一（无分类）」 = Overall CSV 直接读
2. 「应用（有分类）」 = 7 个分类 CSV 联结，每行一个 (cat_csv, app)
3. 对每行:
   类型 (M)         = 该行所在的分类 CSV 名（如 Social）
   类型调整1 (N)    = IF(该 APP 在所有分类 CSV 里 TotalTime 最大值 == 本行) THEN M ELSE ""
   类型调整2 (O)    = IF N == "" THEN ""
                     ELSE IF 人工规则匹配 THEN 人工规则值
                     ELSE IF L/P > 0.5 THEN N ELSE ""
   统一时长 (P)     = VLOOKUP Overall sheet → 该 APP 的 Total Time（如果不在 Overall 则用 L 兜底）
4. 「排序」 sheet:
   每个 APP 一行 (来自人工分类 sheet 的全部条目)
   类型 (J)         = IF 人工规则有 THEN 人工规则cat ELSE 类型调整2(英文)
   统一时长 (K)     = VLOOKUP TT&KWAI → 替换 ELSE 应用（有分类）的统一时长
5. 「汇总」 sheet:
   按 类型 (J) 分组累加 统一时长 (K)

最终中文垂类来自 ENG_TO_CN 映射 + 人工规则。
"""

import json
import os
import config

# 英文 CSV 类目 → 中文垂类（仅这 6 个直接映射，其余靠人工分类）
ENG_TO_CN = {
    'Social': '社交',
    'Games': '游戏',
    'Music': '音乐/音频',
    'News & Magazines': '新闻资讯',
    'Books & Reference': '在线阅读',
    'Shopping': '电商',
}
# 注意：'Photo & Video' 不在此映射 —— 该 CSV 里的 APP 仅在被人工指派为
# 「泛短视频/长视频/直播」时才进入对应垂类，否则不参与累加
# 「直播/长视频/社区/浏览器/搜索/生活服务」完全靠人工分类

CATEGORIES_ZH = config.CATEGORIES_ZH


def load_manual_rules(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'manual_rules.json')
    if not os.path.exists(path):
        return {'rules': {}, 'tt_kwai': {}}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def run(csv_data, tiktok_min=None, kwai_min=None, manual_rules_path=None):
    """
    csv_data: dict[str, list[{name, time}]]
        Required keys: 'Overall', 'Social', 'Photo & Video', 'Music',
        'News & Magazines', 'Books & Reference', 'Games', 'Shopping'
        time 单位: 分钟（与 data.ai 网页 CSV 直接读出一致）
    tiktok_min/kwai_min: 分钟数, override TT/Kwai 统一时长（不传则用 manual_rules.tt_kwai 默认值）
    """
    manual = load_manual_rules(manual_rules_path)
    rules_raw = manual.get('rules', {})  # name → {cat, tag, ext_time}
    # 大小写不敏感的规则索引
    rules = {k.lower(): v for k, v in rules_raw.items()}
    def lookup_rule(name):
        return rules.get(name.lower())
    tt_kwai = dict(manual.get('tt_kwai', {}))
    if tiktok_min is not None:
        tt_kwai['TikTok'] = float(tiktok_min)
    if kwai_min is not None:
        tt_kwai['Kwai'] = float(kwai_min)

    # ---- Step 1: Overall sheet → app_unified[name] = Total Time ----
    overall = {item['name']: float(item['time'])
               for item in csv_data.get('Overall', [])
               if item.get('name') and item.get('time')}

    # ---- Step 2: 应用（有分类）—— 7 个分类 CSV 联结 ----
    # 每行: (csv_cat, name, time_in_csv)
    cat_csvs = {k: v for k, v in csv_data.items() if k != 'Overall'}
    cat_app_time = {}  # name → {csv_cat: time}
    for csv_cat, items in cat_csvs.items():
        for item in items:
            name = item.get('name')
            t = float(item.get('time') or 0)
            if not name or t <= 0:
                continue
            cat_app_time.setdefault(name, {})[csv_cat] = t

    # ---- Step 3: 计算 类型调整1 (cat1) + 类型调整2 (cat2) ----
    # cat1 = 该 APP 在所有分类 CSV 里 TotalTime 最大者所在的 CSV
    # cat2 = 人工规则覆盖 OR (cat1 中 L/P > 0.5)
    name_to_cat2 = {}  # name → English/Chinese cat
    for name, csv_times in cat_app_time.items():
        max_csv = max(csv_times.items(), key=lambda x: x[1])
        cat1 = max_csv[0]      # English
        max_t = max_csv[1]
        # P = 统一时长 = overall[name] 兜底用 max_t
        P = overall.get(name, max_t)
        if lookup_rule(name):
            name_to_cat2[name] = lookup_rule(name)['cat']  # Chinese
        elif max_t / P > 0.5:
            name_to_cat2[name] = cat1  # 英文
        # else: cat2="" 不分类

    # 加上人工规则中 tag=1 的 ext_time（不在 CSV 中也能加）
    for name, rule in rules_raw.items():
        if rule.get('tag') == 1:
            name_to_cat2[name] = rule['cat']

    # ---- Step 4: 「排序」sheet 的统一时长（每 app 唯一）----
    # K = VLOOKUP TT&KWAI → 替换 ELSE 应用（有分类）的统一时长 (= overall[name] 或 max_t)
    name_unified = {}
    for name, cat2 in name_to_cat2.items():
        if name in tt_kwai:
            name_unified[name] = float(tt_kwai[name])
        elif name in overall:
            name_unified[name] = overall[name]
        else:
            # 人工规则添加的 APP（不在任何 CSV）
            rule = rules.get(name, {})
            if rule.get('tag') == 1 and rule.get('ext_time'):
                name_unified[name] = float(rule['ext_time'])
            elif name in cat_app_time:
                # 兜底：用分类 CSV 里最大值
                name_unified[name] = max(cat_app_time[name].values())

    # ---- Step 5: 累加 cat_total + 收集每类 APP ----
    cat_apps = {c: [] for c in CATEGORIES_ZH}
    cat_total = {c: 0.0 for c in CATEGORIES_ZH}

    for name, cat2 in name_to_cat2.items():
        # 英文 → 中文
        zh_cat = ENG_TO_CN.get(cat2, cat2)
        if zh_cat in cat_apps:
            t = name_unified.get(name, 0)
            if t > 0:
                cat_apps[zh_cat].append({'name': name, 'time': t})
                cat_total[zh_cat] += t

    # ---- Step 5b: APP 合并（如 WhatsApp Messenger + WhatsApp Business）----
    MERGE_GROUPS = getattr(config, 'APP_MERGE_GROUPS', {})
    # MERGE_GROUPS: {merged_name: [original_name1, original_name2, ...]}
    # 默认: WhatsApp Messenger & WhatsApp Business
    if not MERGE_GROUPS:
        MERGE_GROUPS = {
            'WhatsApp Messenger & WhatsApp Business': ['WhatsApp Messenger', 'WhatsApp Business'],
        }
    for merged_name, originals in MERGE_GROUPS.items():
        for cat in cat_apps:
            originals_in_cat = [a for a in cat_apps[cat] if a['name'] in originals]
            if len(originals_in_cat) >= 2:
                merged_time = sum(a['time'] for a in originals_in_cat)
                cat_apps[cat] = [a for a in cat_apps[cat] if a['name'] not in originals]
                cat_apps[cat].append({'name': merged_name, 'time': merged_time})

    # ---- Step 6: 排序 + Top5 + 其他 ----
    result = {}
    top_n = getattr(config, 'TOP_N_PER_CATEGORY', 5)
    for cat in CATEGORIES_ZH:
        apps = sorted(cat_apps[cat], key=lambda x: -x['time'])
        for a in apps:
            a['display_time'] = a['time'] / 1e9
        top5 = apps[:top_n]
        rest_sum = sum(a['time'] for a in apps[top_n:])
        result[cat] = {
            'total': cat_total[cat] / 1e9,
            'top5': top5,
            'others': rest_sum / 1e9,
            'all_apps': apps,
        }

    # ---- Step 7: unknown ----
    unknown = []
    for name, t in overall.items():
        if name not in name_to_cat2 and t / 1e9 > 0.5:
            unknown.append({'name': name, 'time': t / 1e9})
    unknown.sort(key=lambda x: -x['time'])

    grand_total = sum(cat_total.values()) / 1e9

    return {
        'categories': result,
        'unknown': unknown,
        'grand_total': grand_total,
    }
