import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["DATAAI_API_KEY"]
COUNTRY = "BR"
DEVICE = "PHONE"
TOP_N = 1000

CATEGORIES_ZH = [
    "社交", "泛短视频", "直播", "长视频", "社区",
    "新闻资讯", "在线阅读", "浏览器/搜索", "音乐/音频",
    "游戏", "电商", "生活服务",
]

# data.ai category name → our Chinese category (None = not directly mapped as a bucket)
DATAAI_TO_ZH = {
    "Overall":          None,
    "Social":           "社交",
    "Photo & Video":    None,           # 长视频 uses Overall口径; this CSV is backup
    "News & Magazines": "新闻资讯",
    "Books & Reference":"在线阅读",
    "Music":            "音乐/音频",
    "Games":            "游戏",
    "Shopping":         "电商",
}

# Categories whose totals use Application Time (from category dataset), not Overall
CSV_APP_TIME_CATS = {"游戏", "电商", "在线阅读", "音乐/音频"}

# Display-locked values for Top5 (minutes, raw precision).
# Only affects Top5 display/sort; never affects category totals.
# Update monthly.
DISPLAY_OVERRIDES = {
    "Google":                          15529088421,
    "Netflix":                         15761750498,
    "Globo Play":                       3667878849,
    "Amazon Prime Video":               2334800042,
    "Max: Stream HBO, TV, & Movies":     929547703,
    "disney+":                          1099946852,
    "ReelShort":                         681207706,
    "DramaBox - movies and drama":       588892111,
    "Pluto.tv":                          353125330,
    "Uber":                             2533700127,
    "iFood Delivery de Comida":         2238241528,
    "99Taxis":                          1667569928,
    "inDrive":                           265380709,
    "Booking.com":                       373162010,
    "Airbnb":                            298177036,
    "Lalamove Driver":                   362383601,
    "waze":                            11890547649,
}
