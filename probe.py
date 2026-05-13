"""
Probe the data.ai API to discover the correct endpoint path and response field names.
Run:  python probe.py
Output is printed to stdout so you can review the response structure.
"""

import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("DATAAI_API_KEY", "")
if not API_KEY:
    sys.exit("ERROR: DATAAI_API_KEY not set in .env")

HEADERS_VARIANTS = [
    {"Authorization": f"Bearer {API_KEY}"},
    {"X-API-KEY": API_KEY},
    {"api_key": API_KEY},
]

ENDPOINT_CANDIDATES = [
    "https://api.data.ai/v1.3/intelligence/usage/metrics",
    "https://api.data.ai/v1.3/intelligence/usage/app-metrics",
    "https://api.data.ai/v1.3/usage/app-metrics",
    "https://api.data.ai/v1.3/apps/usage",
    "https://api.data.ai/v1.3/intelligence/app-usage",
    "https://api.data.ai/v1.3/intelligence/usage",
    "https://api.data.ai/v1.3/usage",
]

# Minimal param set for the probe (Overall, BR, 2025-07)
PARAM_VARIANTS = [
    # variant A – common REST style
    {
        "countries":  "BR",
        "categories": "Overall",
        "device_types": "PHONE",
        "start_date": "2025-07-01",
        "end_date":   "2025-07-31",
        "limit": 5,
    },
    # variant B – plural list style
    {
        "country":   "BR",
        "category":  "Overall",
        "device":    "phone",
        "date":      "2025-07",
        "limit": 5,
    },
    # variant C – granularity explicit
    {
        "countries":    ["BR"],
        "categories":   ["Overall"],
        "device_types": ["PHONE"],
        "granularity":  "monthly",
        "date":         "2025-07",
        "limit": 5,
    },
]


def try_request(url, headers, params):
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        return r.status_code, r.text[:2000]
    except Exception as e:
        return None, str(e)


def main():
    print("=" * 70)
    print("data.ai API endpoint probe")
    print("=" * 70)

    found = []
    for url in ENDPOINT_CANDIDATES:
        for hdr in HEADERS_VARIANTS:
            for params in PARAM_VARIANTS:
                status, body = try_request(url, hdr, params)
                tag = f"[{status}]" if status else "[ERR]"
                short_hdr = list(hdr.keys())[0]
                print(f"\n{tag}  {url}")
                print(f"     header={short_hdr}  params_variant={list(params.keys())[:3]}")
                if status and status < 400:
                    print("  *** SUCCESS ***")
                    print("  Response (first 2000 chars):")
                    print("  " + body[:2000])
                    found.append((url, hdr, params, status, body))
                    # Pretty-print JSON if possible
                    try:
                        data = json.loads(body)
                        print("\n  Pretty JSON:")
                        print("  " + json.dumps(data, indent=2, ensure_ascii=False)[:3000])
                    except Exception:
                        pass
                    break
                else:
                    snippet = body[:120].replace("\n", " ")
                    print(f"     response: {snippet}")
            if found:
                break
        if found:
            break

    print("\n" + "=" * 70)
    if found:
        url, hdr, params, status, body = found[0]
        print(f"WORKING ENDPOINT: {url}")
        print(f"WORKING HEADER  : {hdr}")
        print(f"WORKING PARAMS  : {params}")
        print("\nUpdate BASE_URL and FETCH_PARAMS in fetch.py accordingly.")
        _analyze_fields(body)
    else:
        print("No working endpoint found.")
        print("Please check:")
        print("  1. DATAAI_API_KEY in .env is correct")
        print("  2. Your subscription includes Usage Intelligence")
        print("  3. Try running: curl -H 'Authorization: Bearer $DATAAI_API_KEY' <url>")


def _analyze_fields(body):
    try:
        data = json.loads(body)
    except Exception:
        return
    # Find the first list element
    items = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v:
                items = v
                break
    if not items:
        return
    first = items[0]
    print("\nFields in first record:")
    for k, v in first.items():
        print(f"  {k!r}: {v!r}")
    # Guess field mappings
    name_candidates = [k for k in first if "name" in k.lower() or "app" in k.lower()]
    time_candidates = [k for k in first if "time" in k.lower() or "minutes" in k.lower() or "usage" in k.lower()]
    rank_candidates = [k for k in first if "rank" in k.lower()]
    cat_candidates  = [k for k in first if "cat" in k.lower() or "genre" in k.lower()]
    print(f"\nLikely name field : {name_candidates}")
    print(f"Likely time field : {time_candidates}")
    print(f"Likely rank field : {rank_candidates}")
    print(f"Likely cat  field : {cat_candidates}")
    print("\nUpdate FIELD_MAP in fetch.py with the correct keys.")


if __name__ == "__main__":
    main()
