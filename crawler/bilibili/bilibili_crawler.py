import requests
import time
import json

# ========== 配置区，修改这里 ==========
BV = "BV1xxxxxxxxx"  # 替换你的视频BV号
SLEEP_TIME = 1.2  # 请求间隔，防封禁，不要小于1秒
# ====================================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com"
}


# 1. 获取视频oid
def get_oid(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    res = requests.get(url, headers=headers)
    data = res.json()
    if data["code"] != 0:
        print("获取视频信息失败：", data["message"])
        return None
    return data["data"]["aid"]


# 2. 循环抓取所有一级评论
def get_all_main_comments(oid):
    all_comments = []
    next_cursor = 0  # 分页游标初始值
    while True:
        params = {
            "oid": oid,
            "type": 1,  # 1=视频评论固定值
            "mode": 3,  # 3=按热度排序，2=按时间
            "next": next_cursor
        }
        url = "https://api.bilibili.com/x/v2/reply/main"
        res = requests.get(url, headers=headers, params=params)
        resp = res.json()
        if resp["code"] != 0:
            print("接口报错：", resp["message"])
            break
        data = resp["data"]
        # 当前页一级评论
        page_comments = data.get("replies", [])
        if not page_comments:
            break
        all_comments.extend(page_comments)
        print(f"已抓取 {len(all_comments)} 条一级评论")
        # 更新下一页游标
        cursor_info = data["cursor"]
        next_cursor = cursor_info["next"]
        # 判断是否最后一页
        if cursor_info["is_end"]:
            break
        time.sleep(SLEEP_TIME)
    return all_comments


# 3. 保存评论到本地JSON文件
def save_comments(comments):
    with open("b站一级评论.json", "w", encoding="utf-8") as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)
    print(f"抓取完成，共 {len(comments)} 条一级评论，已保存到 b站一级评论.json")


if __name__ == "__main__":
    oid = get_oid(BV)
    if oid:
        comments = get_all_main_comments(oid)
        save_comments(comments)
