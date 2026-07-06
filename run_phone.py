"""
run_phone.py — phone-only / All Phones API entrypoint.

This is the single-month equivalent of:
  fetch_phone.py <month> -> pipeline.run(raw_cache_phone_<month>.json) -> export Excel

Use this when matching the 2026-05 CSV-import output where Social = 397.08 bn.
"""

import argparse
import os
import sys

import export
import fetch
import pipeline
from fetch_phone import PHONE_DATASETS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--country", default="BR")
    ap.add_argument("--use-cache", action="store_true", help="Use raw_cache_phone_<month>.json if present")
    ap.add_argument("--tiktok", type=float, help="TikTok override, in billion minutes")
    ap.add_argument("--kwai", type=float, help="Kwai override, in billion minutes")
    ap.add_argument("--out", help="Output xlsx path")
    args = ap.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    cache_path = os.path.join(root, f"raw_cache_phone_{args.month}.json")
    out_path = args.out or os.path.join(root, "output", f"巴西数据底稿_{args.month}.xlsx")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    if args.use_cache and os.path.exists(cache_path):
        print(f"📂 从 phone-only 缓存读: {cache_path}")
        csv_data = fetch.load_raw(cache_path)
    else:
        print(f"🌐 从 data.ai API 拉取 phone-only / All Phones: BR/{args.month}")
        fetch.DATASETS = PHONE_DATASETS
        csv_data = fetch.fetch_month(args.month, country=args.country)
        fetch.save_raw(csv_data, cache_path)
        print(f"✓ 缓存已保存: {cache_path}")

    print("\n⚙️  运行 pipeline...")
    tiktok_min = args.tiktok * 1e9 if args.tiktok is not None else None
    kwai_min = args.kwai * 1e9 if args.kwai is not None else None
    result = pipeline.run(csv_data, tiktok_min=tiktok_min, kwai_min=kwai_min, month=args.month)

    print("\n📊 各类合计:")
    for cat, payload in result["categories"].items():
        print(f"   {cat:<14} {payload['total']:>7.2f} bn")
    print(f"   {'合计':<14} {result['grand_total']:>7.2f} bn")

    if result["unknown"]:
        print(f"\n⚠️  未分类 APP (>0.5 bn, 共 {len(result['unknown'])}):")
        for item in result["unknown"][:10]:
            print(f"   {item['name']:<35} {item['time']:.2f} bn")

    print("\n📝 导出 Excel...")
    export.export(result, args.month, out_path)
    print(f"✓ 已生成: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except fetch.QuotaExhausted as e:
        print(f"❌ API 配额耗尽: {e}")
        sys.exit(1)
