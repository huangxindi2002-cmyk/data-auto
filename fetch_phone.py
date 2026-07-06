"""
fetch_phone.py — 临时口径对照脚本：复用 fetch.py 全部逻辑，
仅把 DATASETS 的 device 参数从 android/ios 改为 android_phone/iphone。
输出到 raw_cache_phone_<month>.json，不影响现有 raw_cache_<month>.json。
"""
import fetch
import sys

PHONE_DATASETS = [
    ('Overall', [
        ('all-android', 'android_phone', 'OVERALL'),
        ('ios',         'iphone',        'Overall'),
    ]),
    ('Social', [
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > SOCIAL'),
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > COMMUNICATION'),
        ('ios',         'iphone',        'Overall > Social Networking'),
    ]),
    ('Photo & Video', [
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > VIDEO_PLAYERS'),
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > PHOTOGRAPHY'),
        ('ios',         'iphone',        'Overall > Photo and Video'),
    ]),
    ('Music', [
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > MUSIC_AND_AUDIO'),
        ('ios',         'iphone',        'Overall > Music'),
    ]),
    ('News & Magazines', [
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > NEWS_AND_MAGAZINES'),
        ('ios',         'iphone',        'Overall > News'),
    ]),
    ('Books & Reference', [
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > BOOKS_AND_REFERENCE'),
        ('ios',         'iphone',        'Overall > Books'),
    ]),
    ('Games', [
        ('all-android', 'android_phone', 'OVERALL > GAME'),
        ('ios',         'iphone',        'Overall > Games'),
    ]),
    ('Shopping', [
        ('all-android', 'android_phone', 'OVERALL > APPLICATION > SHOPPING'),
        ('ios',         'iphone',        'Overall > Shopping'),
    ]),
]

if __name__ == '__main__':
    month = sys.argv[1]
    fetch.DATASETS = PHONE_DATASETS
    data = fetch.fetch_month(month, country='BR')
    out = f'raw_cache_phone_{month}.json'
    fetch.save_raw(data, out)
    print(f'\n✓ saved: {out}')
