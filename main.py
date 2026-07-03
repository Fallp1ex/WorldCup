# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse  # 引入 HTML 响应类
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

from routers import users, admin, predict, forum

app = FastAPI(title="世界杯预测系统")

app.include_router(users.router, prefix="/user", tags=["用户模块"])
app.include_router(admin.router, tags=["开发者后台"])
app.include_router(predict.router, prefix="/predict", tags=["朋友互动预测"])
app.include_router(forum.router)
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# 【核心修改】：根目录直接返回我们的 index.html 网页
@app.get("/", response_class=HTMLResponse)
def read_root():
    # 读取同目录下的 index.html 文件并返回
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html 文件未找到，请检查路径！</h1>"

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
