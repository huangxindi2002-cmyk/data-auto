"""
Fetch 8 datasets from data.ai Usage Intelligence API.

Two-phase design to avoid rate-limiting:
  Phase 1: fetch all 16 usage-ranking lists (all-android + ios per category)
           with 60s cool-down between calls
  Phase 2: resolve all unique product_ids → unified_product_name in parallel
           (cached to disk; subsequent runs skip this step)
  Phase 3: combine iOS + Android by name, build final dicts

Return value of fetch_all():
{
  "overall":  [{"name": str, "time": float_bn_min, "rank": int}, ...],
  "social":   {app_name: application_time_bn_min},
  "video":    {app_name: application_time_bn_min},
  "news":     {app_name: application_time_bn_min},
  "books":    {app_name: application_time_bn_min},
  "music":    {app_name: application_time_bn_min},
  "games":    {app_name: application_time_bn_min},
  "shopping": {app_name: application_time_bn_min},
}
"""

import calendar
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import config

# ── Confirmed endpoints (probed 2025-05-11) ───────────────────────────────────
_USAGE_URL   = "https://api.data.ai/v1.3/intelligence/apps/{market}/usage-ranking"
_DETAILS_URL = "https://api.data.ai/v1.3/apps/{market}/app/{pid}/details"
_AUTH        = {"Authorization": f"Bearer {config.API_KEY}"}
_CACHE_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "product_id_cache.json")
_RAW_CACHE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Category paths (verified by probing) ─────────────────────────────────────
_CATEGORIES = [
    # (key,       android_category_path,                              ios_category_path)
    ("overall",  "OVERALL",                                           "Overall"),
    ("social",   "OVERALL > APPLICATION > SOCIAL",                    "Overall > Social Networking"),
    ("video",    "OVERALL > APPLICATION > VIDEO_PLAYERS",             "Overall > Photo and Video"),
    ("news",     "OVERALL > APPLICATION > NEWS_AND_MAGAZINES",        "Overall > News"),
    ("books",    "OVERALL > APPLICATION > BOOKS_AND_REFERENCE",       "Overall > Books"),
    ("music",    "OVERALL > APPLICATION > MUSIC_AND_AUDIO",           "Overall > Music"),
    ("games",    "OVERALL > GAME",                                    "Overall > Games"),
    ("shopping", "OVERALL > APPLICATION > SHOPPING",                  "Overall > Shopping"),
]

# ── Disk cache: "android:20600000013820" → "WhatsApp Messenger" ───────────────
_name_cache: dict = {}

def _load_cache():
    global _name_cache
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, encoding="utf-8") as f:
                _name_cache = json.load(f)
        except Exception:
            _name_cache = {}

def _save_cache():
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_name_cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"  Warning: could not save cache: {e}")


def _raw_cache_path(month):
    return os.path.join(_RAW_CACHE_DIR, f"raw_cache_{month}.json")


def _load_raw(month):
    """Phase 1 断点续传：加载已经拉到的 raw 数据。Returns {(key, platform): [...]} or {}."""
    path = _raw_cache_path(month)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # JSON 不支持 tuple key，反序列化 "key|platform" → (key, platform)
        return {tuple(k.split("|")): v for k, v in data.items()}
    except Exception as e:
        print(f"  Warning: could not load raw cache: {e}")
        return {}


def _save_raw(raw, month):
    """每次成功调用后落盘 raw 数据，支持中断续传。"""
    try:
        serializable = {f"{k[0]}|{k[1]}": v for k, v in raw.items()}
        with open(_raw_cache_path(month), "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False)
    except Exception as e:
        print(f"  Warning: could not save raw cache: {e}")


# ── Phase 1: raw usage-ranking fetch ─────────────────────────────────────────

def _month_range(month_str):
    y, m = map(int, month_str.split("-"))
    last = calendar.monthrange(y, m)[1]
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"


def _fetch_usage_raw(market, device, category, month, retries=4):
    """Fetch usage-ranking list. Returns raw list of records.
    429 时优先用 Retry-After 头，否则指数退避 (60, 120, 240, 480s)."""
    start, end = _month_range(month)
    params = {
        "countries":   config.COUNTRY,
        "categories":  category,
        "device":      device,
        "granularity": "monthly",
        "start_date":  start,
        "end_date":    end,
        "limit":       config.TOP_N,
    }
    url = _USAGE_URL.format(market=market)
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=_AUTH, params=params, timeout=30)
            r.raise_for_status()
            return r.json().get("list", [])
        except requests.HTTPError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                ra = e.response.headers.get("Retry-After")
                wait = int(ra) if ra and ra.isdigit() else 60 * (2 ** attempt)
                print(f"\n  [429] usage-ranking rate-limited. Waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise
        except requests.RequestException:
            if attempt < retries - 1:
                time.sleep(10)
                continue
            raise


def _fetch_all_raw(month, inter_call_delay=5):
    """
    Phase 1: fetch all 16 usage-ranking datasets.
    Returns {(key, platform): [(product_id, total_minutes), ...]}

    自适应延迟：成功调用之间只等 inter_call_delay 秒（默认 5s），
    遇到 429 时由 _fetch_usage_raw 内部退避。

    断点续传：每次成功后落盘到 raw_cache_{month}.json，
    崩溃重启时跳过已完成的数据集。
    """
    raw = _load_raw(month)
    if raw:
        print(f"  Resumed from raw cache: {len(raw)}/16 datasets already fetched.", flush=True)

    calls = [(key, "all-android", "android_phone", ac, "android")
             for key, ac, _ in _CATEGORIES] + \
            [(key, "ios", "iphone", ic, "ios")
             for key, _, ic in _CATEGORIES]

    total = len(calls)
    first_call = True
    for i, (key, market, device, category, platform) in enumerate(calls):
        if (key, platform) in raw:
            print(f"  [{i+1}/{total}] {key}/{platform} ... cached, skip", flush=True)
            continue
        if not first_call:
            time.sleep(inter_call_delay)
        first_call = False
        print(f"  [{i+1}/{total}] {key}/{platform} ({category[:40]})...", end=" ", flush=True)
        records = _fetch_usage_raw(market, device, category, month)
        pairs = [(r["product_id"], r.get("total_minutes", 0)) for r in records
                 if r.get("product_id") and r.get("total_minutes") is not None]
        raw[(key, platform)] = pairs
        print(f"{len(pairs)} records", flush=True)
        _save_raw(raw, month)

    return raw


# ── Phase 2: name resolution ─────────────────────────────────────────────────

def _resolve_one(platform, pid, retries=3):
    """Resolve one product_id → unified_product_name. Writes to _name_cache.
    429 时优先用 Retry-After 头，否则指数退避；并在 stderr 打印以便诊断限速。"""
    cache_key = f"{platform}:{pid}"
    if cache_key in _name_cache:
        return _name_cache[cache_key]

    details_market = "google-play" if platform == "android" else "ios"
    url = _DETAILS_URL.format(market=details_market, pid=pid)

    for attempt in range(retries):
        try:
            r = requests.get(url, headers=_AUTH, timeout=15)
            if r.status_code == 200:
                name = r.json().get("product", {}).get("unified_product_name") or None
                _name_cache[cache_key] = name
                return name
            elif r.status_code == 400:
                _name_cache[cache_key] = None
                return None
            elif r.status_code == 429:
                ra = r.headers.get("Retry-After")
                wait = int(ra) if ra and ra.isdigit() else 60 * (2 ** attempt)
                print(f"\n  [429] details {platform}:{pid} (attempt {attempt+1}/{retries}). "
                      f"Waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            else:
                _name_cache[cache_key] = None
                return None
        except requests.RequestException as e:
            if attempt < retries - 1:
                print(f"\n  [net] {platform}:{pid} {type(e).__name__}; retry in 5s...",
                      flush=True)
                time.sleep(5)
                continue
            _name_cache[cache_key] = None
            return None
    _name_cache[f"{platform}:{pid}"] = None
    return None


def _resolve_all_names(raw, delay_between_calls=2.0):
    """
    Phase 2: resolve all unique product_ids across all datasets sequentially.
    Sequential (not parallel) to stay well within daily API quota.
    Saves cache every 50 calls so progress survives interruption.
    """
    needed = []
    seen = set()
    for (key, platform), pairs in raw.items():
        for pid, _ in pairs:
            cache_key = f"{platform}:{pid}"
            if cache_key not in _name_cache and (platform, pid) not in seen:
                needed.append((platform, pid))
                seen.add((platform, pid))

    if not needed:
        cached_names = sum(len(p) for p in raw.values())
        print(f"  All {cached_names} IDs already cached. No API calls needed.")
        return

    total = len(needed)
    est_min = int(total * delay_between_calls / 60)
    print(f"  Resolving {total} uncached IDs sequentially "
          f"(~{est_min} min at {delay_between_calls}s/call)...", flush=True)

    for i, (platform, pid) in enumerate(needed):
        _resolve_one(platform, pid)
        if delay_between_calls > 0:
            time.sleep(delay_between_calls)
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{total} resolved...", flush=True)
            _save_cache()

    _save_cache()
    resolved = sum(1 for v in _name_cache.values() if v)
    print(f"  Done. Cache: {len(_name_cache)} entries ({resolved} named).")


# ── Phase 3: combine into final datasets ─────────────────────────────────────

def _build_datasets(raw):
    """
    Phase 3: combine Android + iOS by name for each category.
    Returns the final datasets dict.
    """
    result = {}

    for key, _, _ in _CATEGORIES:
        combined: dict[str, float] = {}

        for platform in ("android", "ios"):
            pairs = raw.get((key, platform), [])
            for pid, raw_mins in pairs:
                name = _name_cache.get(f"{platform}:{pid}")
                if not name:
                    continue
                try:
                    t = float(raw_mins) / 1e9
                except (TypeError, ValueError):
                    continue
                combined[name] = combined.get(name, 0.0) + t

        if key == "overall":
            sorted_apps = sorted(combined.items(), key=lambda x: x[1], reverse=True)
            result["overall"] = [
                {"name": name, "time": t, "rank": rank}
                for rank, (name, t) in enumerate(sorted_apps, 1)
            ]
        else:
            result[key] = combined

    return result


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_all(month, inter_call_delay=5):
    """
    Fetch all 8 datasets for the given month (e.g. '2025-07').

    inter_call_delay: seconds between SUCCESSFUL usage-ranking calls (default 5s).
    Total Phase 1 time ≈ 16 × 5s ≈ 1.5 min（无 429 时）.
    遇 429 由 _fetch_usage_raw 自动退避。
    Phase 1 中断后再跑会从 raw_cache_{month}.json 续传。
    Phase 2 is fast when cache is warm (subsequent runs).
    """
    _load_cache()
    print(f"  Cache loaded: {len(_name_cache)} entries.", flush=True)

    print("\n  Phase 1: fetching usage-ranking data...", flush=True)
    raw = _fetch_all_raw(month, inter_call_delay=inter_call_delay)

    print("\n  Phase 2: resolving app names...", flush=True)
    _resolve_all_names(raw)

    print("\n  Phase 3: building combined datasets...", flush=True)
    return _build_datasets(raw)
