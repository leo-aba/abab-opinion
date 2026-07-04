"""
Bilibili 视频信息爬虫测试脚本
==============================
功能：根据 Bilibili 视频 URL 爬取视频元信息，存入 MySQL videos 表。
用法：修改下方 VIDEO_URL 后直接运行 `python test/bilibili/video_info_crawler_test.py`
"""

import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pymysql
import requests
from dotenv import load_dotenv

# ========== 配置区 ==========
VIDEO_URL = "https://www.bilibili.com/video/BV1HfT46AEkh/?spm_id_from=333.1007.tianma.2-2-5.click"  # 替换为目标视频链接或 BV 号
UPSERT = False  # True=已存在时更新, False=已存在时跳过
# ============================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}


def extract_bvid(url_or_bv: str) -> str | None:
    """从 Bilibili URL 或裸 BV 号中提取 BV ID。"""
    match = re.search(r"BV[0-9A-Za-z]{10}", url_or_bv)
    return match.group(0) if match else None


def fetch_video_info(bvid: str) -> dict | None:
    """调用 Bilibili API 获取视频元信息，返回与 videos 表对齐的 dict。"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] 请求 Bilibili API 失败: {e}")
        return None

    data = resp.json()
    if data.get("code") != 0:
        print(f"[ERROR] API 返回错误: code={data.get('code')}, message={data.get('message')}")
        return None

    video = data["data"]
    owner = video.get("owner", {})
    stat = video.get("stat", {})

    # 处理 pubdate（unix timestamp → datetime 字符串）
    publish_time = None
    pubdate = video.get("pubdate")
    if pubdate:
        publish_time = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "id": str(uuid.uuid4()),
        "platform": "bilibili",
        "platform_video_id": video.get("bvid", bvid),
        "title": video.get("title", ""),
        "description": video.get("desc") or None,
        "cover_url": video.get("pic") or None,
        "uploader_name": owner.get("name") or None,
        "uploader_id": str(owner["mid"]) if owner.get("mid") else None,
        "url": f"https://www.bilibili.com/video/{bvid}/",
        "publish_time": publish_time,
        "duration_seconds": video.get("duration"),
        "comment_count": stat.get("reply", 0),
        "view_count": stat.get("view"),
        "like_count": stat.get("like"),
        "analysis_status": "pending",
    }


def _video_exists(cursor, platform: str, platform_video_id: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM videos WHERE platform = %s AND platform_video_id = %s LIMIT 1",
        (platform, platform_video_id),
    )
    return cursor.fetchone() is not None


def save_to_database(conn, info: dict, upsert: bool = False) -> str:
    """
    将视频信息写入 videos 表。
    返回: "inserted" | "updated" | "skipped"
    """
    cursor = conn.cursor()

    if _video_exists(cursor, info["platform"], info["platform_video_id"]):
        if not upsert:
            print(f"[SKIP] 视频已存在: {info['platform_video_id']} — {info['title']}")
            return "skipped"

        update_sql = """
            UPDATE videos SET
                title = %s, description = %s, cover_url = %s,
                uploader_name = %s, uploader_id = %s, url = %s,
                publish_time = %s, duration_seconds = %s,
                comment_count = %s, view_count = %s, like_count = %s,
                updated_at = NOW()
            WHERE platform = %s AND platform_video_id = %s
        """
        cursor.execute(
            update_sql,
            (
                info["title"], info["description"], info["cover_url"],
                info["uploader_name"], info["uploader_id"], info["url"],
                info["publish_time"], info["duration_seconds"],
                info["comment_count"], info["view_count"], info["like_count"],
                info["platform"], info["platform_video_id"],
            ),
        )
        conn.commit()
        print(f"[OK] 已更新: {info['platform_video_id']} — {info['title']}")
        return "updated"

    insert_sql = """
        INSERT INTO videos (
            id, platform, platform_video_id, title, description,
            cover_url, uploader_name, uploader_id, url,
            publish_time, duration_seconds, comment_count,
            view_count, like_count, analysis_status
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
    """
    cursor.execute(
        insert_sql,
        (
            info["id"], info["platform"], info["platform_video_id"],
            info["title"], info["description"],
            info["cover_url"], info["uploader_name"], info["uploader_id"],
            info["url"],
            info["publish_time"], info["duration_seconds"],
            info["comment_count"],
            info["view_count"], info["like_count"],
            info["analysis_status"],
        ),
    )
    conn.commit()
    print(f"[OK] 已插入: {info['platform_video_id']} — {info['title']}")
    return "inserted"


def main():
    # --- 步骤 0: 加载 .env 获取数据库配置 ---
    project_root = Path(__file__).resolve().parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"[WARN] 未找到 .env 文件: {env_path}")

    # --- 步骤 1: 提取 BV ID ---
    bvid = extract_bvid(VIDEO_URL)
    if not bvid:
        print(f"[ERROR] 无法从输入中提取 BV ID: {VIDEO_URL}")
        print("支持的格式: https://www.bilibili.com/video/BVxxx/  或  BVxxx")
        sys.exit(1)
    print(f"[INFO] BV ID: {bvid}")

    # --- 步骤 2: 获取视频信息 ---
    info = fetch_video_info(bvid)
    if not info:
        print("[ERROR] 获取视频信息失败，退出。")
        sys.exit(1)

    print(f"  标题:     {info['title']}")
    print(f"  UP主:     {info['uploader_name']} (UID: {info['uploader_id']})")
    print(f"  播放量:   {info['view_count']}")
    print(f"  评论数:   {info['comment_count']}")
    print(f"  点赞数:   {info['like_count']}")
    print(f"  时长:     {info['duration_seconds']} 秒")
    if info["publish_time"]:
        print(f"  发布时间: {info['publish_time']}")

    # --- 步骤 3: 连接数据库并写入 ---
    db_config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "opinion_analytics"),
        "charset": "utf8mb4",
    }
    print(f"\n[INFO] 连接数据库: {db_config['host']}:{db_config['port']}/{db_config['database']}")

    try:
        conn = pymysql.connect(**db_config)
    except pymysql.Error as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        sys.exit(1)

    try:
        result = save_to_database(conn, info, upsert=UPSERT)
        print(f"\n[DONE] 操作结果: {result}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
