from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import database

router = APIRouter()

# ==================== 【数据模型】 ====================
class PredictModel(BaseModel):
    username: str
    match_id: str  # 保持字符串类型，对接前端滚轮
    predicted_winner: str

class LeaderboardItemModel(BaseModel):
    username: str
    score: int  #猜对场次
    attended_count: int   # 新前端：参加场次
    total_graded: int  # 已经结算的场次
    unsettled_count: int  # 新前端：未结算场次
    all_count : int # 管理员录入场次
    accuracy: str # 正确率：猜对场次/参与场次
    accuracy_attended : str # 参与率：参加场次/结算场次

# ==================== 【接口逻辑】 ====================
@router.get("/matches")
def get_matches():
    return {
        match_id: database.normalize_match(match_id, match)
        for match_id, match in database.MATCHES_DATABASE.items()
    }

@router.post("/submit")
def make_prediction(prediction: PredictModel):
    # 1. 基础验证
    if prediction.username not in database.USER_DATABASE:
        raise HTTPException(status_code=400, detail="请先注册账号！")
    if prediction.match_id not in database.MATCHES_DATABASE:
        raise HTTPException(status_code=400, detail="找不到这场比赛！")

    predict_blocked, predict_until = database.is_user_restricted(prediction.username, "predict")
    if predict_blocked:
        raise HTTPException(
            status_code=403,
            detail=f"你的账号已被封禁，解除时间：{predict_until.strftime('%Y-%m-%d %H:%M')}"
        )
    
    match = database.MATCHES_DATABASE[prediction.match_id]
    if database.is_match_locked(match):
        if match.get("result") is not None:
            raise HTTPException(status_code=400, detail="该赛事已录入真实赛果，已截止提交预测！")
        raise HTTPException(status_code=400, detail="该赛事已到开赛时间，预测入口已关闭！")

    # 💡 【顺便优化】：去重逻辑
    # 如果用户之前对这场比赛有过预测，先在列表中清除老记录，实现“覆盖更新”
    database.PREDICTIONS_DATABASE = [
        p for p in database.PREDICTIONS_DATABASE 
        if not (p["username"] == prediction.username and p["match_id"] == prediction.match_id)
    ]
    
    # 2. 写入新预测
    database.PREDICTIONS_DATABASE.append({
        "username": prediction.username,
        "match_id": prediction.match_id,
        "predicted_winner": prediction.predicted_winner,
        "submitted_at": database.now_iso()
    })
    database.log_event(
        "prediction_submit",
        f"{prediction.username} 提交预测：{prediction.match_id} -> {prediction.predicted_winner}",
        actor=prediction.username
    )
    database.save_to_disk() # 数据写进硬盘
    return {"message": "预测提交成功！"}

@router.get("/leaderboard", response_model=List[LeaderboardItemModel])
def get_leaderboard():
    # 1. 🎯 彻底锁死总场次：直接数管理员录入了多少场比赛
    all_count = len(database.MATCHES_DATABASE)
    
    # 2. 🎯 【核心修改】全局精算大盘未结算场次（定义②）
    # 遍历全量比赛库，看一共有多少场比赛的 result 还是 None
    if isinstance(database.MATCHES_DATABASE, dict):
        matches_list = database.MATCHES_DATABASE.values()
    else:
        matches_list = database.MATCHES_DATABASE
        
    system_unsettled_count = 0
    for m in matches_list:
        res = m.get("result") if isinstance(m, dict) else getattr(m, "result", None)
        if res is None:
            system_unsettled_count += 1

    # 3. 🎯 初始化所有注册用户：让所有人不论是否预测，全部整齐划一地上榜
    user_stats = {}
    for username in database.USER_DATABASE:
        user_stats[username] = {
            "username": username,
            "score": 0,               # 猜对场次
            "attended_count": 0,      # 参加场次
            "total_graded": 0,        # 已经结算的场次
            "unsettled_count": system_unsettled_count,  # 🎯 所有人共享相同的大盘未开奖数
            "all_count": all_count,   # 所有人共享相同的总场次
            "accuracy": "0.0%",
            "accuracy_attended": "0.0%"
        }
    
    # 4. 🎯 剥离遍历预测表：只用来累加个人的“参加场次”和“猜对得分”
    for p in database.PREDICTIONS_DATABASE:
        uname = p.get("username") if isinstance(p, dict) else getattr(p, "username", None)
        m_id = p.get("match_id") if isinstance(p, dict) else getattr(p, "match_id", None)
        pred = p.get("predicted_winner") if isinstance(p, dict) else getattr(p, "predicted_winner", None)
        
        if uname in user_stats:
            # 只要他提交了预测，他的个人参加场次 +1
            user_stats[uname]["attended_count"] += 1
            
            # 单独去比赛库看这场比赛出结果了没有
            match = database.MATCHES_DATABASE.get(m_id) if isinstance(database.MATCHES_DATABASE, dict) else next((m for m in database.MATCHES_DATABASE if m.get("id") == m_id), None)
            
            if match:
                result = match.get("result") if isinstance(match, dict) else getattr(match, "result", None)
                if result is not None:
                    user_stats[uname]["total_graded"] += 1  # 该用户已结算的比赛 +1
                    if pred == result:
                        user_stats[uname]["score"] += 1     # 猜对 +1
                    # 💡 注意：此处不再设置个人 unsettled_count 的累加，彻底剥离个人未结算逻辑

    # 5. 🎯 统一计算所有人的百分比率
    leaderboard_list = []
    for uname, stat in user_stats.items():
        attended = stat["attended_count"]
        score = stat["score"]
        
        # 正确率 = 猜对场次 / 参加场次
        if attended > 0:
            stat["accuracy"] = f"{(score / attended * 100):.1f}%"
        else:
            stat["accuracy"] = "0.0%"
            
        # 参与率 = 参加场次 / 管理员录入总场次 (all_count)
        if all_count > 0:
            stat["accuracy_attended"] = f"{(attended / all_count * 100):.1f}%"
        else:
            stat["accuracy_attended"] = "0.0%"
            
        leaderboard_list.append(stat)
        
    # 6. 排序规则：先按猜对场次降序，相同再按正确率降序
    leaderboard_list.sort(
        key=lambda x: (x["score"], float(x["accuracy"].replace("%", ""))), 
        reverse=True
    )
    
    return leaderboard_list

@router.get("/my/{username}")
def get_user_predictions(username: str):
    user_preds = {}
    for p in database.PREDICTIONS_DATABASE:
        if p["username"] == username:
            match = database.MATCHES_DATABASE.get(p["match_id"], {})
            user_preds[p["match_id"]] = {
                "predicted_winner": p["predicted_winner"],
                "submitted_at": p.get("submitted_at"),
                "team_a": match.get("team_a"),
                "team_b": match.get("team_b"),
                "result": match.get("result"),
                "date": match.get("date")
            }
    return user_preds
