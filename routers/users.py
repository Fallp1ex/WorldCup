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
    
    # 1. 使用 .strip() 去掉用户名首尾的空格，防止有人输入 "   " 钻空子
    username = user_data.username.strip()
    password = user_data.password

    # 2. 核心判断：如果名字为空，直接拦截并报错
    if not username:
        raise HTTPException(status_code=400, detail="注册失败：用户名不能为空！")
        
    if client_ip in database.REGISTERED_IPS:
        raise HTTPException(status_code=400, detail="注册失败：该 IP 已经注册过账号！")
    if username in database.USER_DATABASE:
        raise HTTPException(status_code=400, detail="注册失败：用户名已存在！")

    # 3. 写入数据库（注意：这里存入的是处理干净后的 username）
    database.USER_DATABASE[username] = {"password": password, "ip": client_ip}
    database.REGISTERED_IPS.add(client_ip)
    
    database.save_to_disk()  
    return {"message": "注册成功！"}