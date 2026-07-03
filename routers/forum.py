from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import database

router = APIRouter(prefix="/forum", tags=["比赛论坛"])


class ForumPostModel(BaseModel):
    username: str
    match_id: str
    content: str
    reply_to_id: int | None = None


@router.get("/matches")
def forum_matches():
    matches = []
    for match_id, match in database.MATCHES_DATABASE.items():
        post_count = sum(1 for post in database.FORUM_POSTS_DATABASE if post["match_id"] == match_id)
        item = database.normalize_match(match_id, match)
        item["post_count"] = post_count
        matches.append(item)
    matches.sort(key=lambda item: item.get("start_time") or "", reverse=False)
    return matches


@router.get("/posts/{match_id}")
def forum_posts(match_id: str):
    if match_id not in database.MATCHES_DATABASE:
        raise HTTPException(status_code=404, detail="找不到对应比赛论坛")

    posts = [post for post in database.FORUM_POSTS_DATABASE if post["match_id"] == match_id]
    post_map = {post["id"]: {**post, "replies": []} for post in posts}
    roots = []
    for post in sorted(posts, key=lambda item: item.get("created_at", "")):
        reply_to_id = post.get("reply_to_id")
        if reply_to_id and reply_to_id in post_map:
            post_map[reply_to_id]["replies"].append(post_map[post["id"]])
        else:
            roots.append(post_map[post["id"]])
    return roots


@router.post("/posts")
def create_forum_post(data: ForumPostModel):
    username = data.username.strip()
    content = data.content.strip()

    if username not in database.USER_DATABASE:
        raise HTTPException(status_code=404, detail="请先登录后再发言")
    if data.match_id not in database.MATCHES_DATABASE:
        raise HTTPException(status_code=404, detail="找不到对应比赛论坛")
    if not content:
        raise HTTPException(status_code=400, detail="发言内容不能为空")
    if len(content) > 300:
        raise HTTPException(status_code=400, detail="单条发言请控制在 300 字以内")

    banned, ban_until = database.is_user_restricted(username, "forum")
    if banned:
        raise HTTPException(
            status_code=403,
            detail=f"你的账号已被封禁，解除时间：{ban_until.strftime('%Y-%m-%d %H:%M')}"
        )

    reply_to_id = data.reply_to_id
    if reply_to_id is not None:
        parent = next((post for post in database.FORUM_POSTS_DATABASE if post["id"] == reply_to_id and post["match_id"] == data.match_id), None)
        if not parent:
            raise HTTPException(status_code=404, detail="被回复的评论不存在")

    post = {
        "id": database.next_forum_post_id(),
        "match_id": data.match_id,
        "username": username,
        "content": content,
        "created_at": database.now_iso(),
        "reply_to_id": reply_to_id
    }
    database.FORUM_POSTS_DATABASE.append(post)
    database.log_event(
        "forum_post_create",
        f"{username} 在 {data.match_id} 发表论坛内容：{content}" + (f"（回复 #{reply_to_id}）" if reply_to_id else ""),
        actor=username
    )
    database.save_to_disk()
    return {"message": "发言成功", "post": post}


@router.delete("/posts/{post_id}")
def delete_forum_post(post_id: int):
    for index, post in enumerate(database.FORUM_POSTS_DATABASE):
        if post["id"] == post_id:
            deleted = database.FORUM_POSTS_DATABASE.pop(index)
            database.log_event(
                "forum_post_delete",
                f"管理员删除论坛评论 #{post_id}：{deleted['username']} - {deleted['content']}",
                actor="admin"
            )
            database.save_to_disk()
            return {"message": "评论已删除"}
    raise HTTPException(status_code=404, detail="找不到该评论")


@router.get("/search")
def search_forum_posts(keyword: str = ""):
    query = keyword.strip().lower()
    if not query:
        return []

    results = []
    for post in database.FORUM_POSTS_DATABASE:
        if query in post["content"].lower() or query in post["username"].lower():
            match = database.MATCHES_DATABASE.get(post["match_id"], {})
            results.append({
                **post,
                "team_a": match.get("team_a"),
                "team_b": match.get("team_b"),
                "date": match.get("date")
            })
    results.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return results
