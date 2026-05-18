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


DETAILS_URL = "https://api.data.ai/v1.3/apps/{market}/app/{pid}/details"
CACHE_PATH = os.path.join(os.path.dirname(__file__), 'product_id_cache.json')


def _load_name_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_name_cache(cache):
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def _resolve_name(platform, pid, api_key):
    """platform: 'android' | 'ios'. Returns unified_product_name or None.

    429 处理：
    - 带 Retry-After 且 < 120s → 视为每分钟限速，sleep 后重试一次
    - 否则视为日配额耗尽，抛 QuotaExhausted
    """
    details_market = 'google-play' if platform == 'android' else 'ios'
    url = DETAILS_URL.format(market=details_market, pid=pid)
    headers = {"Authorization": f"Bearer {api_key}"}
    for attempt in range(2):
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 429:
            retry_after = int(r.headers.get('Retry-After', '0') or 0)
            if 0 < retry_after < 120 and attempt == 0:
                time.sleep(retry_after + 1)
                continue
            raise QuotaExhausted(f"details {platform}:{pid}: 429 quota exhausted")
        if r.status_code != 200:
            return None
        return r.json().get('product', {}).get('unified_product_name')
    return None


def fetch_month(month, country='BR', api_key=None):
    """
    month: 'YYYY-MM' 格式
    Returns: dict[csv_cat_eng, list[{name, package_id, time(min)}]]

    Ranking API 不返回 product_name，必须二次调用 details 端点解析名字。
    使用 product_id_cache.json 缓存 pid → name，避免重复调用。
    """
    yr, mo = month.split('-')
    start_date = f"{yr}-{mo}-01"
    import calendar
    end_day = calendar.monthrange(int(yr), int(mo))[1]
    end_date = f"{yr}-{mo}-{end_day:02d}"

    if api_key is None:
        api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("API_KEY 未设置（请检查 .env DATAAI_API_KEY）")

    name_cache = _load_name_cache()

    # ── Phase 1: 拉 ranking，收集 (platform, pid) → time，每个 CSV 一份 ──
    # csv_raw[csv_name][(platform, pid)] = total_minutes
    csv_raw = {}
    all_pids = set()  # set of (platform, pid)
    for csv_name, sources in DATASETS:
        csv_raw[csv_name] = {}
        for market, device, category in sources:
            print(f"  fetching {csv_name} ← {market}/{device}/{category[:50]}...")
            items = _fetch_one(market, device, category, country, start_date, end_date, api_key)
            platform = 'ios' if market == 'ios' else 'android'
            for it in items:
                pid = it.get('product_id')
                if pid is None:
                    continue
                try:
                    t = float(it.get('total_minutes', 0))
                except (TypeError, ValueError):
                    continue
                if t <= 0:
                    continue
                key = (platform, pid)
                csv_raw[csv_name][key] = csv_raw[csv_name].get(key, 0.0) + t
                all_pids.add(key)
            time.sleep(1)  # 友好限速，避免 429

    # ── Phase 2: 解析名字（缓存未命中的 pid 串行调 details, 间隔 2s）──
    def cache_key(plat, pid):
        return f"{plat}:{pid}"

    to_resolve = [(p, pid) for (p, pid) in all_pids
                  if name_cache.get(cache_key(p, pid)) in (None,)]
    if to_resolve:
        print(f"\n🔍 解析 {len(to_resolve)} 个新 product_id 的名字（缓存命中 {len(all_pids) - len(to_resolve)}/{len(all_pids)}），4 线程并发...")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        cache_lock = threading.Lock()

        def _worker(plat, pid):
            try:
                return plat, pid, _resolve_name(plat, pid, api_key)
            except QuotaExhausted as e:
                return plat, pid, e
            except Exception:
                return plat, pid, None

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(_worker, plat, pid) for (plat, pid) in to_resolve]
            completed = 0
            quota_hit = False
            for fut in as_completed(futures):
                plat, pid, result = fut.result()
                if isinstance(result, QuotaExhausted):
                    quota_hit = True
                    continue
                with cache_lock:
                    name_cache[cache_key(plat, pid)] = result
                completed += 1
                if completed % 50 == 0:
                    print(f"   {completed}/{len(to_resolve)} ...")
                    with cache_lock:
                        _save_name_cache(name_cache)
        _save_name_cache(name_cache)
        if quota_hit:
            raise QuotaExhausted("daily quota hit during name resolution")
        resolved_ok = sum(1 for (p, pid) in to_resolve if name_cache.get(cache_key(p, pid)))
        print(f"   ✓ 解析完成（{resolved_ok} 成功 / {len(to_resolve)} 总）")

    # ── Phase 3: 按 name 合并 Android+iOS, 构建输出 ──
    csv_data = {}
    for csv_name, raw in csv_raw.items():
        merged = {}  # name → {package_id, time}
        for (plat, pid), t in raw.items():
            name = name_cache.get(cache_key(plat, pid))
            if not name:
                continue
            if name in merged:
                merged[name]['time'] += t
            else:
                merged[name] = {'name': name, 'package_id': str(pid), 'time': t}
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
