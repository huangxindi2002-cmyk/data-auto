"""
csv_loader.py — 读取 data.ai 网页下载的 8 个分类 CSV

CSV 格式（前 9 行是元信息，第 10 行起是 column header + data）:
  Line 1: "Top Apps by Total Time"
  ...
  Line 10: "Unified App,Unified App Name,...,Total Time"
  Line 11+: 数据行

会自动识别 CSV 文件的分类：
- 文件内含 "Category Adjustments: Filtered to Social" → "Social"
- 等等
"""

import csv
import os
import re

CATEGORY_HINTS = {
    'social': 'Social',
    'photo & video': 'Photo & Video',
    'photo&video': 'Photo & Video',
    'games': 'Games',
    'music': 'Music',
    'news & magazines': 'News & Magazines',
    'news&magazines': 'News & Magazines',
    'books & reference': 'Books & Reference',
    'books&reference': 'Books & Reference',
    'shopping': 'Shopping',
    'overall': 'Overall',
}


def load_csv_file(path):
    """
    Returns (csv_cat: str, apps: list[dict])
        apps: [{name, package_id, time(min)}, ...]
    """
    with open(path, encoding='utf-8') as f:
        text = f.read()

    # 探测分类：找 "Category,XXX" 行
    csv_cat = None
    head_lines = text[:2000].split('\n')
    for line in head_lines:
        m = re.match(r'^Category\s*,\s*(.+?)\s*$', line)
        if m:
            cat_str = m.group(1).strip().lower().rstrip('"').lstrip('"')
            # Overall 类目（含 "Overall, Entertainment" / "Overall" / 空值）
            if cat_str.startswith('overall') or cat_str == '':
                csv_cat = 'Overall'
            else:
                csv_cat = CATEGORY_HINTS.get(cat_str, m.group(1).strip())
            break
    if csv_cat is None:
        if not any(l.startswith('Category,') for l in head_lines):
            csv_cat = 'Overall'

    # 找 header line
    lines = text.split('\n')
    hdr_idx = -1
    for i, line in enumerate(lines):
        if 'Unified App' in line and 'Total Time' in line:
            hdr_idx = i
            break
    if hdr_idx == -1:
        return csv_cat, []

    rdr = csv.reader(lines[hdr_idx:])
    header = next(rdr)
    name_col = header.index('Unified App Name')
    time_col = header.index('Total Time')
    pkg_col = header.index('Unified App') if 'Unified App' in header else -1

    apps = []
    for row in rdr:
        if len(row) <= time_col:
            continue
        name = row[name_col].strip()
        if not name:
            continue
        try:
            t = float(row[time_col].replace(',', '').strip())
        except (ValueError, AttributeError):
            continue
        apps.append({
            'name': name,
            'package_id': row[pkg_col] if pkg_col >= 0 and pkg_col < len(row) else None,
            'time': t,
        })
    return csv_cat, apps


def load_csv_dir(directory):
    """
    Returns dict[csv_cat, apps]
    """
    csv_data = {}
    for fn in sorted(os.listdir(directory)):
        if not fn.lower().endswith('.csv'):
            continue
        path = os.path.join(directory, fn)
        cat, apps = load_csv_file(path)
        if cat is None:
            print(f"  ⚠️  skipped (cannot detect category): {fn}")
            continue
        if cat in csv_data:
            print(f"  ⚠️  duplicate category {cat}, merging")
            csv_data[cat].extend(apps)
        else:
            csv_data[cat] = apps
        print(f"  ✓ {fn[:50]}  →  {cat}: {len(apps)} apps")
    return csv_data
