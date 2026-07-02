# routers/users.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import database  # 导入公共数据

router = APIRouter()

class UserModel(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(user_data: UserModel, request: Request):
    client_ip = request.client.host
    username = user_data.username.strip()
    password = user_data.password

    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空，请重新输入")
    if not password:
        raise HTTPException(status_code=400, detail="密码不能为空，请重新输入")
    if username in database.USER_DATABASE:
        raise HTTPException(status_code=400, detail="该用户名已存在，请重新输入")

    database.USER_DATABASE[username] = {
        "password": password,
        "ip": client_ip,
        "created_at": request.headers.get("date")
    }
    database.REGISTERED_IPS.add(client_ip)

    database.log_event("user_register", f"用户 {username} 注册成功", actor=username)
    database.save_to_disk()
    return {"message": "注册成功！"}

@router.post("/login")
def login(user_data: UserModel, request: Request):
    username = user_data.username.strip()
    password = user_data.password

    if username not in database.USER_DATABASE:
        raise HTTPException(status_code=404, detail="该用户不存在，请注册后登录")

    user_record = database.USER_DATABASE[username]
    if user_record.get("password") != password:
        raise HTTPException(status_code=400, detail="密码错误，请重新输入")

    user_record["last_login_ip"] = request.client.host
    database.log_event("user_login", f"用户 {username} 登录成功", actor=username)
    database.save_to_disk()
    return {"message": "登录成功！", "username": username}
