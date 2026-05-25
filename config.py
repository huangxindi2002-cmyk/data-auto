"""
config.py — 项目配置
"""
import os

# API 配置（从 .env 读）
def _get_api_key():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('DATAAI_API_KEY='):
                    return line.split('=', 1)[1].strip()
    return os.environ.get('DATAAI_API_KEY', '')

API_KEY = _get_api_key()
COUNTRY = "BR"
TOP_N = 1000  # data.ai API limit 上限

# 12 个中文垂类（输出 Excel/treemap 列序）
CATEGORIES_ZH = [
    "社交", "泛短视频", "直播", "中长视频", "短剧", "社区",
    "新闻资讯", "在线阅读", "浏览器/搜索", "音乐/音频",
    "游戏", "电商", "生活服务", "AI",
]

# 每个大类显示的 Top N（其余归为「其他」）
TOP_N_PER_CATEGORY = 5

# APP 合并：把多条记录合成一条（如 WhatsApp Messenger + WhatsApp Business）
APP_MERGE_GROUPS = {
    'WhatsApp Messenger & WhatsApp Business': [
        'WhatsApp Messenger',
        'WhatsApp Business',
    ],
}
