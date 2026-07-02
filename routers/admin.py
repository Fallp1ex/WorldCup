# # routers/admin.py
# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# import database

# router = APIRouter()

# class AddMatchModel(BaseModel):
#     team_a: str
#     team_b: str

# @router.post("/add_match")
# def add_match(match: AddMatchModel):
#     current_id = database.CONFIG["match_id_counter"]
    
#     database.MATCHES_DATABASE[current_id] = {
#         "team_a": match.team_a,
#         "team_b": match.team_b,
#         "result": None
#     }
    
#     # 计数器自动加 1
#     database.CONFIG["match_id_counter"] += 1
#     database.save_to_disk() # 👈 就加这一句！数据直接写进硬盘！
#     return {"message": f"成功添加比赛 [ID: {current_id}]: {match.team_a} VS {match.team_b}"}
    

# @router.delete("/delete_match/{match_id}")
# def delete_match(match_id: int):
#     if match_id not in database.MATCHES_DATABASE:
#         raise HTTPException(status_code=404, detail="找不到这场比赛！")
    
#     deleted = database.MATCHES_DATABASE.pop(match_id)
#     # 清理关联的预测
#     database.PREDICTIONS_DATABASE = [p for p in database.PREDICTIONS_DATABASE if p["match_id"] != match_id]
#     database.save_to_disk() # 👈 就加这一句！数据直接写进硬盘！
#     return {"message": f"已成功删除比赛：{deleted['team_a']} VS {deleted['team_b']}"}

# @router.get("/dashboard")
# def admin_dashboard():
#     return {
#         "总注册人数": len(database.USER_DATABASE),
#         "当前所有比赛": database.MATCHES_DATABASE,
#         "收到的所有预测": database.PREDICTIONS_DATABASE
#     }


# # ================ (追加在 routers/admin.py 最末尾) ================

# # 定义录入赛果的数据模型
# class SetResultModel(BaseModel):
#     match_id: int
#     result: str  # 必须填 “主队名”、“客队名” 或者 “平局”

# @router.post("/set_result")
# def set_result(data: SetResultModel):
#     # 1. 检查比赛是否存在
#     if data.match_id not in database.MATCHES_DATABASE:
#         raise HTTPException(status_code=404, detail="找不到这场比赛！")
    
#     match = database.MATCHES_DATABASE[data.match_id]
    
#     # 2. 校验输入的赛果是否合法（防止手抖打错字）
#     allowed_results = [match["team_a"], match["team_b"], "平局"]
#     if data.result not in allowed_results:
#         raise HTTPException(
#             status_code=400, 
#             detail=f"赛果不合法！必须是 '{match['team_a']}'、'{match['team_b']}' 或 '平局' 之一"
#         )
    
#     # 3. 录入赛果
#     database.MATCHES_DATABASE[data.match_id]["result"] = data.result
#     database.save_to_disk() # 👈 就加这一句！数据直接写进硬盘！
#     return {"message": f"比赛 [ID: {data.match_id}] 赛果已成功录入为: {data.result}"}

# routers/admin.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import database

router = APIRouter(prefix="/admin", tags=["开发者后台"])
ADMIN_PASSWORD = "123456"

# 1. 这里的模型增加了 date 字段
class AddMatchModel(BaseModel):
    team_a: str
    team_b: str
    date: str  

# 2. 这里的 match_id 类型从 int 改为 str
class SetResultModel(BaseModel):
    match_id: str  
    result: str

class AdminAuthModel(BaseModel):
    password: str

@router.get("/users")
def list_users():
    users = []
    for username, info in database.USER_DATABASE.items():
        users.append({
            "username": username,
            "ip": info.get("ip", ""),
            "created_at": info.get("created_at"),
            "last_login_ip": info.get("last_login_ip")
        })
    users.sort(key=lambda item: item["username"].lower())
    return users

@router.delete("/delete_user/{username}")
def delete_user(username: str):
    if username not in database.USER_DATABASE:
        raise HTTPException(status_code=404, detail="找不到该用户")

    user_info = database.USER_DATABASE.pop(username)
    user_ip = user_info.get("ip")
    if user_ip:
        still_used = any(info.get("ip") == user_ip for info in database.USER_DATABASE.values())
        if not still_used and user_ip in database.REGISTERED_IPS:
            database.REGISTERED_IPS.remove(user_ip)

    database.PREDICTIONS_DATABASE = [
        p for p in database.PREDICTIONS_DATABASE if p["username"] != username
    ]

    database.log_event("user_delete", f"删除用户 {username}", actor="admin")
    database.save_to_disk()
    return {"message": f"已删除用户：{username}"}

@router.post("/verify")
def verify_admin(data: AdminAuthModel):
    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=400, detail="密码错误，请重新输入")

    database.log_event("admin_verify", "管理员验证成功", actor="admin")
    database.save_to_disk()
    return {"message": "管理员验证成功"}

@router.post("/add_match")
def add_match(match: AddMatchModel):
    # 清理前后空格
    ta = match.team_a.strip()
    tb = match.team_b.strip()
    dt = match.date.strip()
    
    if not ta or not tb or not dt:
        raise HTTPException(status_code=400, detail="球队名称和比赛时间不能为空！")

    # 🎯 核心逻辑：自动拼接出你想要的动态字符串ID，例如 "阿根廷vs法国 2022Dec26"
    custom_match_id = f"{ta}vs{tb} {dt}"
    reverse_match_id = f"{tb}vs{ta} {dt}"  # 👈 新增：顺便算出主客队颠倒的 ID
    
    if custom_match_id in database.MATCHES_DATABASE or reverse_match_id in database.MATCHES_DATABASE:
        raise HTTPException(status_code=400, detail="该比赛（或对应主客场赛事）已存在，请勿重复添加！")
    
    # 存入大仓库
    database.MATCHES_DATABASE[custom_match_id] = {
        "team_a": ta,
        "team_b": tb,
        "date": dt,
        "result": None
    }

    database.log_event("match_add", f"发布比赛 {custom_match_id}", actor="admin")
    database.save_to_disk()
    return {"message": f"成功发布赛事：{custom_match_id}"}

@router.delete("/delete_match/{match_id}")
def delete_match(match_id: str):  # 改为 str
    if match_id not in database.MATCHES_DATABASE:
        raise HTTPException(status_code=404, detail="找不到这场比赛！")
    
    database.MATCHES_DATABASE.pop(match_id)
    database.PREDICTIONS_DATABASE = [p for p in database.PREDICTIONS_DATABASE if p["match_id"] != match_id]

    database.log_event("match_delete", f"删除比赛 {match_id}", actor="admin")
    database.save_to_disk()
    return {"message": f"已成功删除比赛：{match_id}"}

@router.post("/set_result")
def set_result(data: SetResultModel):
    # 此时 data.match_id 传进来的就是 "阿根廷vs法国 2022Dec26"
    if data.match_id not in database.MATCHES_DATABASE:
        raise HTTPException(status_code=404, detail="找不到这场比赛！请检查比赛标识是否完全一致（注意大小写和空格）。")
    
    match = database.MATCHES_DATABASE[data.match_id]
    allowed_results = [match["team_a"], match["team_b"], "平局"]
    if data.result not in allowed_results:
        raise HTTPException(status_code=400, detail="赛果不合法！")
    
    database.MATCHES_DATABASE[data.match_id]["result"] = data.result

    database.log_event("match_set_result", f"录入赛果 {data.match_id} -> {data.result}", actor="admin")
    database.save_to_disk()
    return {"message": f"赛事 [{data.match_id}] 结果已成功录入为: {data.result}"}

# @router.delete("/delete_match/{match_id}")
# def delete_match(match_id: str):
#     # 1. 检查比赛是否存在
#     if match_id not in database.MATCHES_DATABASE:
#         raise HTTPException(status_code=404, detail="找不到该比赛，删除失败！")
    
#     # 2. 从比赛大仓库中抹除
#     del database.MATCHES_DATABASE[match_id]
    
#     # 3. 💥 核心联动：连带清理所有用户的这场比赛预测，防止账目混乱
#     database.PREDICTIONS_DATABASE = [
#         p for p in database.PREDICTIONS_DATABASE if p["match_id"] != match_id
#     ]
    
#     # 4. 保存到硬盘
#     database.save_to_disk()
    
#     return {"message": f"成功删除赛事及其关联的预测记录！"}
