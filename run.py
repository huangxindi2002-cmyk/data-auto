"""
Entry point.

Usage:
  python run.py --month 2025-07 --tiktok 175.887 --kwai 68.967

  --month   YYYY-MM (required)
  --tiktok  TikTok total time in billion minutes  (from 竞对监控; optional)
  --kwai    Kwai total time in billion minutes    (from 内部看板; optional)
  --out     output .xlsx path (default: 巴西数据底稿_YYYY-MM.xlsx)
"""

import argparse
import sys
import fetch
import pipeline
import export
import config

SMOKE_TARGETS = {
    "社交":     408.53,
    "泛短视频":  509.50,
    "直播":       1.878,
    "长视频":   270.94,
    "社区":      19.12,
    "新闻资讯":   0.750,
    "在线阅读":   8.97,
    "浏览器/搜索": 91.36,
    "音乐/音频":  23.16,
    "游戏":     151.14,
    "电商":      30.34,
    "生活服务":   7.74,
}


def smoke_test(categories_result):
    """Compare against 2025-07 verified targets. Only printed, not a hard failure."""
    print("\n── Smoke test (2025-07 targets) ──────────────────────────────────")
    print(f"{'分类':12}  {'目标':>8}  {'实际':>8}  {'差值':>8}  {'OK?'}")
    print("─" * 55)
    all_ok = True
    for cat, target in SMOKE_TARGETS.items():
        actual = categories_result[cat]["total"]
        diff = actual - target
        ok = abs(diff) < 0.5
        flag = "✓" if ok else "✗"
        if not ok:
            all_ok = False
        print(f"{cat:12}  {target:8.3f}  {actual:8.3f}  {diff:+8.3f}  {flag}")
    print()
    if all_ok:
        print("All targets within ±0.5 十亿分钟  ✓")
    else:
        print("Some targets differ — check classification rules or overrides.")


def main():
    parser = argparse.ArgumentParser(description="巴西数据自动化 → Excel底稿")
    parser.add_argument("--month",  required=True, help="YYYY-MM")
    parser.add_argument("--tiktok", type=float,  default=None,
                        help="TikTok 十亿分钟 (手动覆盖)")
    parser.add_argument("--kwai",   type=float,  default=None,
                        help="Kwai 十亿分钟 (手动覆盖)")
    parser.add_argument("--out",    default=None,
                        help="输出文件路径 (default: 巴西数据底稿_YYYY-MM.xlsx)")
    args = parser.parse_args()

    out_path = args.out or f"巴西数据底稿_{args.month}.xlsx"

    print(f"\n=== data-auto  month={args.month}  country={config.COUNTRY} ===")
    if args.tiktok:
        print(f"  TikTok override: {args.tiktok:.3f} 十亿分钟")
    if args.kwai:
        print(f"  Kwai   override: {args.kwai:.3f} 十亿分钟")

    print("\n[1/3] Fetching datasets...")
    try:
        datasets = fetch.fetch_all(args.month)
    except fetch.QuotaExhausted as e:
        print(f"\n=== 日配额耗尽，今日运行终止 ===")
        print(f"  原因: {e}")
        print(f"  操作: 明日 UTC 00:00（北京 08:00）配额重置后，重跑同样命令即可从缓存续传。")
        print(f"  Excel 未生成（数据不完整）。")
        sys.exit(2)

    print("\n[2/3] Running pipeline...")
    result = pipeline.run(datasets, tiktok_bn=args.tiktok, kwai_bn=args.kwai)

    print(f"\nGrand total: {result['grand_total']:.1f} 十亿分钟")
    print(f"Kwai rank:   No.{result['kwai_rank']}")
    if result["unknown"]:
        print(f"Unknown apps (>{1}十亿分钟): {len(result['unknown'])}")
        for item in result["unknown"][:10]:
            print(f"  {item['name'][:40]:40}  {item['time']:.3f}")

    print("\n[3/3] Exporting Excel...")
    export.export(result, args.month, out_path)

    if args.month == "2025-07":
        smoke_test(result["categories"])

    print("\nDone.")


if __name__ == "__main__":
    main()
