"""
run.py — 主流程：API 拉数 → pipeline → Excel → 触发画图

用法:
  python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967
  python3 run.py --month 2025-07 --tiktok 175.887 --kwai 68.967 --use-cache
  python3 run.py --month 2025-07 --csv-dir /path/to/csvs   # 跳过 API，用本地 CSV
"""

import argparse
import os
import json
import sys

import fetch
import pipeline
import export


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True, help='YYYY-MM')
    ap.add_argument('--tiktok', type=float, help='TikTok 修正时长（十亿分钟）')
    ap.add_argument('--kwai', type=float, help='Kwai 修正时长（十亿分钟）')
    ap.add_argument('--country', default='BR')
    ap.add_argument('--use-cache', action='store_true', help='不拉 API, 用 raw_cache_<month>.json')
    ap.add_argument('--csv-dir', help='跳过 API，从指定目录读 8 个 CSV')
    ap.add_argument('--out', help='输出 Excel 路径，默认 巴西数据底稿_<month>.xlsx')
    ap.add_argument('--no-open', action='store_true', help='完成后不自动打开画图工具')
    args = ap.parse_args()

    month = args.month
    out_path = args.out or f"巴西数据底稿_{month}.xlsx"
    raw_cache_path = os.path.join(os.path.dirname(__file__), f"raw_cache_{month}.json")

    # ── Step 1: 拿到 csv_data ──
    csv_data = None

    if args.csv_dir:
        print(f"📂 从本地 CSV 读: {args.csv_dir}")
        import csv_loader
        csv_data = csv_loader.load_csv_dir(args.csv_dir)
    elif args.use_cache and os.path.exists(raw_cache_path):
        print(f"📂 从缓存读: {raw_cache_path}")
        csv_data = fetch.load_raw(raw_cache_path)
    else:
        print(f"🌐 从 data.ai API 拉取 {month} 数据...")
        try:
            csv_data = fetch.fetch_month(month, country=args.country)
            fetch.save_raw(csv_data, raw_cache_path)
            print(f"✓ 缓存已保存: {raw_cache_path}")
        except fetch.QuotaExhausted as e:
            print(f"❌ API 配额耗尽: {e}")
            if os.path.exists(raw_cache_path):
                print(f"📂 回退到缓存: {raw_cache_path}")
                csv_data = fetch.load_raw(raw_cache_path)
            else:
                print(f"   无可用缓存，请稍后重试或用 --csv-dir")
                sys.exit(1)

    # ── Step 2: pipeline ──
    print(f"\n⚙️  运行 pipeline...")
    tiktok_min = args.tiktok * 1e9 if args.tiktok else None
    kwai_min = args.kwai * 1e9 if args.kwai else None
    result = pipeline.run(csv_data, tiktok_min=tiktok_min, kwai_min=kwai_min)

    print(f"\n📊 各类合计:")
    for cat in result['categories']:
        v = result['categories'][cat]['total']
        print(f"   {cat:<14} {v:>7.2f} bn")
    print(f"   {'合计':<14} {result['grand_total']:>7.2f} bn")

    if result['unknown']:
        print(f"\n⚠️  未分类 APP (>0.5 bn, 共 {len(result['unknown'])}):")
        for u in result['unknown'][:10]:
            print(f"   {u['name']:<35} {u['time']:.2f} bn")
        if len(result['unknown']) > 10:
            print(f"   ... 共 {len(result['unknown'])} 个，建议补 manual_rules.json")

    # ── Step 3: 导出 Excel ──
    print(f"\n📝 导出 Excel...")
    export.export(result, month, out_path)
    print(f"✓ 已生成: {out_path}")

    # ── Step 4: 打开画图工具（自动加载 Excel） ──
    if not args.no_open:
        html_path = os.path.join(os.path.dirname(__file__), 'tools', 'treemap_v2.html')
        if os.path.exists(html_path):
            # 启动一个本地 HTTP server 解决 file:// fetch 的 CORS 问题
            # 把 Excel 复制到 tools/ 同目录下
            import shutil
            tools_dir = os.path.dirname(html_path)
            xlsx_filename = os.path.basename(out_path)
            tools_xlsx = os.path.join(tools_dir, xlsx_filename)
            shutil.copy2(out_path, tools_xlsx)

            # 在 tools/ 启动 http server (port 自动选)
            import http.server, socketserver, threading, socket
            for port in range(8765, 8800):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind(('127.0.0.1', port))
                    sock.close()
                    break
                except OSError:
                    continue
            os.chdir(tools_dir)
            handler = http.server.SimpleHTTPRequestHandler
            httpd = socketserver.TCPServer(('127.0.0.1', port), handler)
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            url = f"http://127.0.0.1:{port}/treemap_v2.html?excel={xlsx_filename}"
            import subprocess
            subprocess.run(['open', url], check=False)
            print(f"🎨 已打开画图工具（本地服务: {url}）")
            print(f"   按 Ctrl+C 停止服务（不停止也可关闭终端）")
            try:
                t.join()
            except KeyboardInterrupt:
                print(f"\n服务停止")
        else:
            print(f"⚠️  未找到 {html_path}")


if __name__ == '__main__':
    main()
