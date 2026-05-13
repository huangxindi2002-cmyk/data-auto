"""
Unit tests for fetch.py — focused on 429 / 配额污染防护：
  1. 3 次连续 429 抛 QuotaExhausted，且不缓存为 None
  2. 1~2 次 429 后 200 应正常缓存名称（重试机制还有效）
  3. 400 仍缓存 None（合法的"app 不存在"）
  4. _resolve_all_names 在 QuotaExhausted 时保存缓存并 re-raise
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import patch, MagicMock
import requests
import fetch


def _mock_response(status=200, json_body=None, headers=None):
    m = MagicMock(spec=requests.Response)
    m.status_code = status
    m.json.return_value = json_body or {}
    m.headers = headers or {}
    return m


def _reset_cache():
    fetch._name_cache = {}


def test_three_429s_raise_quota_exhausted():
    """3 次 429 应抛 QuotaExhausted，且 cache 不被污染（无 None 写入）。"""
    _reset_cache()
    resp_429 = _mock_response(429, headers={"Retry-After": "0"})

    raised = False
    with patch.object(fetch.requests, "get", return_value=resp_429), \
         patch.object(fetch.time, "sleep"):  # 跳过实际等待
        try:
            fetch._resolve_one("ios", "1102452668")
        except fetch.QuotaExhausted:
            raised = True

    assert raised, "应当抛 QuotaExhausted"
    assert "ios:1102452668" not in fetch._name_cache, \
        f"cache 不应被污染：{fetch._name_cache}"


def test_429_then_200_succeeds():
    """前 2 次 429，第 3 次 200 → 应正常缓存名称（重试有效）。"""
    _reset_cache()
    responses = [
        _mock_response(429, headers={"Retry-After": "0"}),
        _mock_response(429, headers={"Retry-After": "0"}),
        _mock_response(200, json_body={"product": {"unified_product_name": "TestApp"}}),
    ]

    with patch.object(fetch.requests, "get", side_effect=responses), \
         patch.object(fetch.time, "sleep"):
        name = fetch._resolve_one("ios", "999")

    assert name == "TestApp", f"应得 TestApp，实际 {name}"
    assert fetch._name_cache["ios:999"] == "TestApp"


def test_400_still_caches_none():
    """400 表示 PID 不存在，缓存 None 是合理的（永久跳过）。"""
    _reset_cache()
    resp_400 = _mock_response(400)

    with patch.object(fetch.requests, "get", return_value=resp_400):
        result = fetch._resolve_one("android", "12345")

    assert result is None
    assert fetch._name_cache["android:12345"] is None


def test_resolve_all_names_quota_propagation():
    """_resolve_all_names 遇 QuotaExhausted 时应保存缓存并 re-raise。"""
    _reset_cache()
    raw = {
        ("overall", "android"): [("100", 1000), ("200", 2000)],
        ("overall", "ios"):     [("300", 3000)],
    }

    # 第一个 PID 成功，第二个抛配额异常
    call_count = [0]
    def fake_resolve(platform, pid, retries=3):
        call_count[0] += 1
        cache_key = f"{platform}:{pid}"
        if call_count[0] == 1:
            fetch._name_cache[cache_key] = "FirstApp"
            return "FirstApp"
        raise fetch.QuotaExhausted("simulated")

    saved = [False]
    def fake_save():
        saved[0] = True

    with patch.object(fetch, "_resolve_one", side_effect=fake_resolve), \
         patch.object(fetch, "_save_cache", side_effect=fake_save), \
         patch.object(fetch.time, "sleep"):
        raised = False
        try:
            fetch._resolve_all_names(raw, delay_between_calls=0)
        except fetch.QuotaExhausted:
            raised = True

    assert raised, "QuotaExhausted 应当向上抛出"
    assert saved[0], "_save_cache 应当在异常时被调用"


def test_network_error_does_not_raise_quota():
    """网络异常不应被误判为配额耗尽（仍走原路径，最终缓存 None）。"""
    _reset_cache()
    with patch.object(fetch.requests, "get", side_effect=requests.ConnectionError("net down")), \
         patch.object(fetch.time, "sleep"):
        result = fetch._resolve_one("ios", "777")

    assert result is None
    assert fetch._name_cache["ios:777"] is None  # 网络异常仍按原逻辑缓存 None


if __name__ == "__main__":
    tests = [
        ("3x429 抛 QuotaExhausted 且不污染 cache", test_three_429s_raise_quota_exhausted),
        ("2x429 后 200 仍能缓存名称",             test_429_then_200_succeeds),
        ("400 仍缓存 None（合法不存在）",          test_400_still_caches_none),
        ("_resolve_all_names 配额异常落盘 + re-raise", test_resolve_all_names_quota_propagation),
        ("网络异常不误判为配额",                  test_network_error_does_not_raise_quota),
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
