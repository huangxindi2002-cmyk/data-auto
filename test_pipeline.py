"""
Unit tests for pipeline.py — focused on fixes:
  1. CSV口径分类 others 用 csv_times (Application Time)，不用 display_time
  2. 社交 others 用 i["time"] (Overall Time)
  3. Overall口径 others 用 i["time"]
  4. DISPLAY_OVERRIDES 缺失 APP 时返回 missing_overrides 列表
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import pipeline


def _with_overrides(overrides, fn):
    """临时替换 config.DISPLAY_OVERRIDES 并恢复。"""
    saved = config.DISPLAY_OVERRIDES
    config.DISPLAY_OVERRIDES = overrides
    try:
        return fn()
    finally:
        config.DISPLAY_OVERRIDES = saved


def test_csv_kou_jing_others_fix():
    """游戏 is CSV口径。Game1 的 display 被覆盖为 120bn (实际 CSV time = 80)。
    修复前: others = 100 - 120 = max(0,-20) = 0 (错)
    修复后: others = 100 - 80 = 20 (对，因为减的是 csv_times[Game1])
    """
    cat_groups = {c: [] for c in config.CATEGORIES_ZH}
    cat_groups["游戏"] = [{"name": "Game1", "time": 100.0, "rank": 1}]
    cat_csv_times = {"游戏": {"Game1": 80.0, "Game2": 20.0}}

    result = _with_overrides(
        {"Game1": 120 * 1e9},
        lambda: pipeline._compute_category("游戏", cat_groups, cat_csv_times),
    )

    assert result["total"] == 100.0, f"total expected 100.0, got {result['total']}"
    assert result["top5"][0]["display_time"] == 120.0, \
        f"display_time expected 120.0 (from override), got {result['top5'][0]['display_time']}"
    assert abs(result["others"] - 20.0) < 0.001, \
        f"others expected 20.0, got {result['others']}"


def test_csv_kou_jing_others_no_override():
    """无 override 时 CSV口径 others 也应正确：cat_total - csv_times[top5]。"""
    cat_groups = {c: [] for c in config.CATEGORIES_ZH}
    cat_groups["电商"] = [
        {"name": "Shopee", "time": 30.0, "rank": 1},
        {"name": "Mercado Libre", "time": 20.0, "rank": 2},
    ]
    cat_csv_times = {"电商": {"Shopee": 32.0, "Mercado Libre": 22.0, "AliExpress": 5.0}}

    result = _with_overrides(
        {},
        lambda: pipeline._compute_category("电商", cat_groups, cat_csv_times),
    )

    expected_total = 32 + 22 + 5  # = 59
    expected_others = 59 - 32 - 22  # = 5
    assert result["total"] == expected_total, f"total: {result['total']}"
    assert abs(result["others"] - expected_others) < 0.001, f"others: {result['others']}"


def test_social_others():
    """社交 cat_total 用 Overall Time，others = cat_total - sum(i.time)。"""
    cat_groups = {c: [] for c in config.CATEGORIES_ZH}
    cat_groups["社交"] = [
        {"name": "WhatsApp Messenger & WhatsApp Business", "time": 200.0, "rank": 1},
        {"name": "Instagram", "time": 100.0, "rank": 2},
        {"name": "Facebook", "time": 50.0, "rank": 3},
        {"name": "SocialX", "time": 10.0, "rank": 10},
        {"name": "SocialY", "time": 5.0, "rank": 11},
        {"name": "SocialZ", "time": 2.0, "rank": 12},
    ]
    cat_csv_times = {"社交": {n: t * 1.2 for n, t in
                              [("WhatsApp Messenger & WhatsApp Business", 200),
                               ("Instagram", 100), ("Facebook", 50)]}}

    result = _with_overrides(
        {},
        lambda: pipeline._compute_category("社交", cat_groups, cat_csv_times),
    )

    expected_total = 200 + 100 + 50 + 10 + 5 + 2  # 367
    top5_sum = 200 + 100 + 50 + 10 + 5
    expected_others = expected_total - top5_sum  # 2
    assert result["total"] == expected_total, f"total: {result['total']}"
    assert abs(result["others"] - expected_others) < 0.001, f"others: {result['others']}"


def test_overall_kou_jing_others_with_override():
    """长视频 (Overall口径)。Netflix 有 override 但不该影响 others（others 用 i.time）。"""
    cat_groups = {c: [] for c in config.CATEGORIES_ZH}
    cat_groups["长视频"] = [
        {"name": "Netflix", "time": 50.0, "rank": 1},
        {"name": "YouTube", "time": 30.0, "rank": 2},
        {"name": "Globo Play", "time": 20.0, "rank": 3},
        {"name": "Other1", "time": 5.0, "rank": 4},
        {"name": "Other2", "time": 4.0, "rank": 5},
        {"name": "Other3", "time": 3.0, "rank": 6},
    ]

    result = _with_overrides(
        {"Netflix": 60 * 1e9},  # 不应影响 cat_total 或 others
        lambda: pipeline._compute_category("长视频", cat_groups, {}),
    )

    expected_total = 50 + 30 + 20 + 5 + 4 + 3  # 112
    top5_sum_actual = 50 + 30 + 20 + 5 + 4    # 109
    expected_others = expected_total - top5_sum_actual  # 3
    assert result["total"] == expected_total, f"total: {result['total']}"
    assert abs(result["others"] - expected_others) < 0.001, f"others: {result['others']}"


def test_display_overrides_warning_missing():
    """DISPLAY_OVERRIDES 中 APP 没出现在 overall 数据里时，应在结果里报告 missing_overrides。"""
    datasets = {
        "overall": [
            {"name": "Netflix", "time": 50.0, "rank": 1},
            {"name": "Instagram", "time": 30.0, "rank": 2},
        ],
        "social": {}, "video": {}, "news": {}, "books": {},
        "music": {}, "games": {}, "shopping": {},
    }
    result = _with_overrides(
        {"Netflix": 60e9, "NoSuchApp": 1e9, "AnotherMissing": 1e9},
        lambda: pipeline.run(datasets),
    )

    assert "NoSuchApp" in result["missing_overrides"]
    assert "AnotherMissing" in result["missing_overrides"]
    assert "Netflix" not in result["missing_overrides"]


def test_display_overrides_warning_empty():
    """DISPLAY_OVERRIDES 全部命中时 missing_overrides 应为空。"""
    datasets = {
        "overall": [
            {"name": "Netflix", "time": 50.0, "rank": 1},
            {"name": "Globo Play", "time": 30.0, "rank": 2},
        ],
        "social": {}, "video": {}, "news": {}, "books": {},
        "music": {}, "games": {}, "shopping": {},
    }
    result = _with_overrides(
        {"Netflix": 60e9, "Globo Play": 30e9},
        lambda: pipeline.run(datasets),
    )
    assert result["missing_overrides"] == []


def test_whatsapp_merge():
    """两个 WhatsApp 都在时应合并；只有一个时仅重命名。"""
    overall = [
        {"name": "WhatsApp Messenger", "time": 200.0, "rank": 1},
        {"name": "WhatsApp Business", "time": 50.0, "rank": 5},
        {"name": "Instagram", "time": 100.0, "rank": 2},
    ]
    merged = pipeline._merge_whatsapp(overall)
    names = [i["name"] for i in merged]
    assert "WhatsApp Messenger & WhatsApp Business" in names
    assert "WhatsApp Business" not in names
    assert "WhatsApp Messenger" not in names
    wa = next(i for i in merged if "WhatsApp" in i["name"])
    assert wa["time"] == 250.0


if __name__ == "__main__":
    tests = [
        ("CSV口径 others 修复 (with DISPLAY_OVERRIDES)",   test_csv_kou_jing_others_fix),
        ("CSV口径 others 无 override 时正确",              test_csv_kou_jing_others_no_override),
        ("社交 others 用 Overall Time",                    test_social_others),
        ("Overall口径 others 不受 DISPLAY_OVERRIDES 影响", test_overall_kou_jing_others_with_override),
        ("DISPLAY_OVERRIDES 缺失项被检出",                 test_display_overrides_warning_missing),
        ("DISPLAY_OVERRIDES 全部命中时无缺失",             test_display_overrides_warning_empty),
        ("WhatsApp 合并逻辑",                              test_whatsapp_merge),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"✓ {name}")
        except AssertionError as e:
            print(f"✗ {name}\n    {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name} [ERROR]\n    {type(e).__name__}: {e}")
            failed += 1
    print()
    if failed:
        print(f"{failed} test(s) failed.")
        sys.exit(1)
    print(f"All {len(tests)} tests passed.")
