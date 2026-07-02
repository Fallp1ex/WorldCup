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

DATA_FILE = "data_storage.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        _disk_data = json.load(f)
        USER_DATABASE = _disk_data.get("users", {})
        REGISTERED_IPS = set(_disk_data.get("ips", []))
        # 💡 核心改动：比赛ID现在天生就是字符串，直接读取即可，删掉 int(k) 转换
        MATCHES_DATABASE = _disk_data.get("matches", {})
        PREDICTIONS_DATABASE = _disk_data.get("predictions", [])
        CONFIG = _disk_data.get("config", {})
        ACTIVITY_LOG = _disk_data.get("activity_log", [])
else:
    USER_DATABASE = {}
    REGISTERED_IPS = set()
    MATCHES_DATABASE = {}
    PREDICTIONS_DATABASE = []
    CONFIG = {}
    ACTIVITY_LOG = []

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
            "config": CONFIG,
            "activity_log": ACTIVITY_LOG
        }, f, ensure_ascii=False, indent=4)
