# # database.py
# import json
# import os

# DATA_FILE = "data_storage.json"

# # --- 核心：程序启动时，自动从硬盘读取老数据 ---
# if os.path.exists(DATA_FILE):
#     with open(DATA_FILE, "r", encoding="utf-8") as f:
#         _disk_data = json.load(f)
#         USER_DATABASE = _disk_data.get("users", {})
#         REGISTERED_IPS = set(_disk_data.get("ips", []))
#         # 注意：JSON的key全是字符串，这里要把比赛ID转回int类型，否则后端逻辑会报错
#         MATCHES_DATABASE = {int(k): v for k, v in _disk_data.get("matches", {}).items()}
#         PREDICTIONS_DATABASE = _disk_data.get("predictions", [])
#         CONFIG = _disk_data.get("config", {"match_id_counter": 1})
# else:
#     # 如果文件不存在，初始化空数据
#     USER_DATABASE = {}
#     REGISTERED_IPS = set()
#     MATCHES_DATABASE = {}
#     PREDICTIONS_DATABASE = []
#     CONFIG = {"match_id_counter": 1}

# # --- 核心：提供一个保存函数，谁修改了数据就调用一下 ---
# def save_to_disk():
#     with open(DATA_FILE, "w", encoding="utf-8") as f:
#         json.dump({
#             "users": USER_DATABASE,
#             "ips": list(REGISTERED_IPS), # set集合转成list才能存JSON
#             "matches": MATCHES_DATABASE,
#             "predictions": PREDICTIONS_DATABASE,
#             "config": CONFIG
#         }, f, ensure_ascii=False, indent=4)

# database.py
import json
import os
from datetime import datetime
from copy import deepcopy

DATA_FILE = "data_storage.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        _disk_data = json.load(f)
        USER_DATABASE = _disk_data.get("users", {})
        REGISTERED_IPS = set(_disk_data.get("ips", []))
        # 💡 核心改动：比赛ID现在天生就是字符串，直接读取即可，删掉 int(k) 转换
        MATCHES_DATABASE = _disk_data.get("matches", {})
        PREDICTIONS_DATABASE = _disk_data.get("predictions", [])
        FORUM_POSTS_DATABASE = _disk_data.get("forum_posts", [])
        CONFIG = _disk_data.get("config", {})
        ACTIVITY_LOG = _disk_data.get("activity_log", [])
else:
    USER_DATABASE = {}
    REGISTERED_IPS = set()
    MATCHES_DATABASE = {}
    PREDICTIONS_DATABASE = []
    FORUM_POSTS_DATABASE = []
    CONFIG = {}
    ACTIVITY_LOG = []

CONFIG.setdefault("forum_post_counter", 1)

TIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
)

def log_event(event_type, detail, actor=None):
    ACTIVITY_LOG.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "type": event_type,
        "actor": actor,
        "detail": detail
    })

def save_to_disk():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": USER_DATABASE,
            "ips": list(REGISTERED_IPS),
            "matches": MATCHES_DATABASE,
            "predictions": PREDICTIONS_DATABASE,
            "forum_posts": FORUM_POSTS_DATABASE,
            "config": CONFIG,
            "activity_log": ACTIVITY_LOG
        }, f, ensure_ascii=False, indent=4)

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        for fmt in TIME_FORMATS:
            try:
                return datetime.strptime(stripped, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(stripped)
        except ValueError:
            return None
    return None

def ensure_user_restrictions(username):
    user = USER_DATABASE.setdefault(username, {})
    restrictions = user.setdefault("restrictions", {})
    if "ban_until" not in restrictions:
        legacy_ban = restrictions.get("predict_until") or restrictions.get("forum_until")
        restrictions["ban_until"] = legacy_ban
    restrictions.pop("predict_until", None)
    restrictions.pop("forum_until", None)
    return restrictions

def get_user_restriction(username, scope=None):
    user = USER_DATABASE.get(username, {})
    restrictions = user.get("restrictions", {})
    if "ban_until" in restrictions:
        return restrictions.get("ban_until")
    return restrictions.get("predict_until") or restrictions.get("forum_until")

def is_user_restricted(username, scope=None):
    until_raw = get_user_restriction(username, scope)
    until = parse_datetime(until_raw)
    if not until:
        return False, None
    now = datetime.now()
    if until <= now:
        ensure_user_restrictions(username)["ban_until"] = None
        return False, None
    return True, until

def set_user_restriction(username, scope, until_iso):
    restrictions = ensure_user_restrictions(username)
    restrictions["ban_until"] = until_iso

def clear_user_restriction(username, scope):
    restrictions = ensure_user_restrictions(username)
    restrictions["ban_until"] = None

def normalize_match(match_id, match):
    item = deepcopy(match)
    item["match_id"] = match_id
    start_time = parse_datetime(item.get("date"))
    item["start_time"] = start_time.isoformat(timespec="minutes") if start_time else None
    item["is_locked"] = is_match_locked(item)
    return item

def is_match_locked(match):
    if match.get("result") is not None:
        return True
    start_time = parse_datetime(match.get("date"))
    if not start_time:
        return False
    return datetime.now() >= start_time

def next_forum_post_id():
    post_id = CONFIG.get("forum_post_counter", 1)
    CONFIG["forum_post_counter"] = post_id + 1
    return post_id
