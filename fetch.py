"""
fetch.py — data.ai API 拉取，结果与网页 CSV 对齐

关键设计:
- device='android' (= phone+tablet) / device='ios' (= iphone+ipad)
- Social = SOCIAL + COMMUNICATION (Android 把 WhatsApp 放 COMMUNICATION)
- Photo & Video = VIDEO_PLAYERS + PHOTOGRAPHY (Android)
- 输出格式: dict[csv_cat_eng, list[{name, package_id, time(min)}]]
  与 csv_loader.load_csv_dir() 完全一致，可直接喂给 pipeline_v2
"""

import os
import time
import json
import requests
import config

API_BASE = "https://api.data.ai/v1.3/intelligence/apps/{market}/usage-ranking"

# 8 个 CSV 数据集。每个对应一个网页下载的 CSV
# (CSV_eng_name, [(market, device, category), ...])
# 每个数据集可能跨多个 (market, device, category)，最后合并
DATASETS = [
    ('Overall', [
        ('all-android', 'android', 'OVERALL'),
        ('ios',         'ios',     'Overall'),
    ]),
    ('Social', [
        ('all-android', 'android', 'OVERALL > APPLICATION > SOCIAL'),
        ('all-android', 'android', 'OVERALL > APPLICATION > COMMUNICATION'),
        ('ios',         'ios',     'Overall > Social Networking'),
    ]),
    ('Photo & Video', [
        ('all-android', 'android', 'OVERALL > APPLICATION > VIDEO_PLAYERS'),
        ('all-android', 'android', 'OVERALL > APPLICATION > PHOTOGRAPHY'),
        ('ios',         'ios',     'Overall > Photo and Video'),
    ]),
    ('Music', [
        ('all-android', 'android', 'OVERALL > APPLICATION > MUSIC_AND_AUDIO'),
        ('ios',         'ios',     'Overall > Music'),
    ]),
    ('News & Magazines', [
        ('all-android', 'android', 'OVERALL > APPLICATION > NEWS_AND_MAGAZINES'),
        ('ios',         'ios',     'Overall > News'),
    ]),
    ('Books & Reference', [
        ('all-android', 'android', 'OVERALL > APPLICATION > BOOKS_AND_REFERENCE'),
        ('ios',         'ios',     'Overall > Books'),
    ]),
    ('Games', [
        ('all-android', 'android', 'OVERALL > GAME'),
        ('ios',         'ios',     'Overall > Games'),
    ]),
    ('Shopping', [
        ('all-android', 'android', 'OVERALL > APPLICATION > SHOPPING'),
        ('ios',         'ios',     'Overall > Shopping'),
    ]),
]


class QuotaExhausted(Exception):
    """API 配额耗尽（HTTP 429）"""


def _get_api_key():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('DATAAI_API_KEY='):
                    return line.split('=', 1)[1].strip()
    return os.environ.get('DATAAI_API_KEY')


def _fetch_one(market, device, category, country, start_date, end_date, key, retry=3):
    url = API_BASE.format(market=market)
    params = dict(
        countries=country,
        categories=category,
        device=device,
        granularity='monthly',
        start_date=start_date,
        end_date=end_date,
        limit=1000,
    )
    headers = {"Authorization": f"Bearer {key}"}
    last_err = None
    for attempt in range(retry):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=60)
            if r.status_code == 429:
                raise QuotaExhausted(f"{market}/{device}/{category}: 429 quota exhausted")
            r.raise_for_status()
            return r.json().get('list', [])
        except QuotaExhausted:
            raise
        except Exception as e:
            last_err = e
            if attempt < retry - 1:
                time.sleep(2 + attempt * 3)
    raise RuntimeError(f"{market}/{device}/{category}: {last_err}")


def fetch_month(month, country='BR', api_key=None):
    """
    month: 'YYYY-MM' 格式
    Returns: dict[csv_cat_eng, list[{name, package_id, time(min)}]]
    """
    yr, mo = month.split('-')
    start_date = f"{yr}-{mo}-01"
    # 月末日期
    import calendar
    end_day = calendar.monthrange(int(yr), int(mo))[1]
    end_date = f"{yr}-{mo}-{end_day:02d}"

    if api_key is None:
        api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("API_KEY 未设置（请检查 .env DATAAI_API_KEY）")

    csv_data = {}
    for csv_name, sources in DATASETS:
        merged = {}  # name → {package_id, time}
        for market, device, category in sources:
            print(f"  fetching {csv_name} ← {market}/{device}/{category[:50]}...")
            items = _fetch_one(market, device, category, country, start_date, end_date, api_key)
            for it in items:
                name = it.get('product_name')
                pid = it.get('product_id')
                t = it.get('total_minutes', 0)
                if not name:
                    continue
                try:
                    t = float(t)
                except (TypeError, ValueError):
                    continue
                if t <= 0:
                    continue
                # 按 unified product name 合并（同一个 APP 在 Android+iOS 各有一份）
                if name in merged:
                    merged[name]['time'] += t
                else:
                    merged[name] = {'name': name, 'package_id': pid, 'time': t}
            time.sleep(1)  # 友好限速，避免 429
        csv_data[csv_name] = list(merged.values())
        total = sum(a['time'] for a in csv_data[csv_name])
        print(f"  ✓ {csv_name}: {len(csv_data[csv_name])} apps, total {total/1e9:.2f} bn min")
    return csv_data


def save_raw(csv_data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(csv_data, f, ensure_ascii=False, indent=1)


def load_raw(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)
