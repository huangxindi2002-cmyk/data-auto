"""
scripts/build_index.py — 扫描 docs/data/ 下的 Excel，生成 index.json
供前端 docs/index.html 列出历史数据
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'docs' / 'data'

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(DATA_DIR.glob('*.xlsx')):
        m = re.search(r'(\d{4}-\d{2})', p.name)
        items.append({
            'file': p.name,
            'month': m.group(1) if m else '',
            'size': p.stat().st_size,
            'mtime': int(p.stat().st_mtime),
        })
    # 倒序：最新的在前
    items.sort(key=lambda x: x['month'], reverse=True)
    out = DATA_DIR / 'index.json'
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✓ {len(items)} 条记录 → {out.relative_to(ROOT)}')

if __name__ == '__main__':
    main()
