"""B站评论爬虫 — 使用 requests 直接调用 B站开放 API
B站评论接口相对开放，不需要 Selenium，直接 HTTP 请求即可

用法：修改下面的 BV 和 MAX_PAGES，然后运行即可
"""

import sys, os, json, time, requests

sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# ========== 配置区 ==========
BV = "BV1JpEd66Ehr"  # 视频BV号
MAX_PAGES = 50        # 最多抓取页数（每页20条）
SLEEP_SEC = 1.2       # 请求间隔（秒），不要小于1秒
# ============================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}


def get_oid(bvid):
    """通过 BV 号获取视频 oid（aid），这是评论接口需要的参数"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    resp = requests.get(url, headers=HEADERS)
    data = resp.json()
    if data["code"] != 0:
        print(f"获取视频信息失败: {data.get('message', '未知错误')}")
        return None
    return data["data"]["aid"]


def fetch_page(oid, cursor=0):
    """抓取一页一级评论"""
    params = {
        "oid": oid,
        "type": 1,          # 1 = 视频评论
        "mode": 3,          # 3 = 按热度, 2 = 按时间
        "next": cursor,
    }
    url = "https://api.bilibili.com/x/v2/reply/main"
    resp = requests.get(url, headers=HEADERS, params=params)
    data = resp.json()
    if data["code"] != 0:
        print(f"  接口报错: {data.get('message', '未知错误')}")
        return None, None, False
    return data["data"]["replies"], data["data"]["cursor"]["next"], data["data"]["cursor"]["is_end"]


def extract_comment_info(c):
    """提取评论中的关键字段，与抖音爬虫保持一致的输出结构"""
    # B站 ctime 是 Unix 时间戳
    ctime = c.get("ctime", 0)
    return {
        "cid": str(c.get("rpid", "")),            # 评论ID（保持字符串类型）
        "text": c.get("content", {}).get("message", ""),
        "create_time": ctime,
        "digg_count": c.get("like", 0),
        "reply_comment_total": c.get("rcount", 0),
        "user": {
            "uid": str(c.get("member", {}).get("mid", "")),
            "nickname": c.get("member", {}).get("uname", ""),
            "avatar": c.get("member", {}).get("avatar", ""),
        },
    }


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_file = os.path.join(out_dir, f"bilibili_comments_{BV}.json")
    tmp_file = os.path.join(out_dir, f"bilibili_comments_{BV}_tmp.json")

    print(f"1. 获取视频信息 (BV: {BV})...")
    oid = get_oid(BV)
    if not oid:
        print("获取 oid 失败，退出")
        return
    print(f"   oid = {oid}")

    print(f"2. 开始抓取评论 (最多 {MAX_PAGES} 页)...")
    all_comments = []
    cursor = 0
    page = 0
    is_end = False

    while not is_end and page < MAX_PAGES:
        page += 1
        print(f"\n   第 {page} 页 (cursor={cursor})...", end=" ", flush=True)

        replies, next_cursor, is_end = fetch_page(oid, cursor)

        if replies is None:
            break

        if not replies:
            print("无更多评论")
            break

        for c in replies:
            all_comments.append(extract_comment_info(c))

        print(f"累计 {len(all_comments)} 条", end="", flush=True)

        cursor = next_cursor  # type: ignore

        # 每10页保存一次临时结果
        if page % 10 == 0:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(all_comments, f, ensure_ascii=False, indent=2)
            print(f" [已保存临时文件]", end="", flush=True)

        print()
        time.sleep(SLEEP_SEC)

    print(f"\n3. 保存结果 ({len(all_comments)} 条评论)...")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_comments, f, ensure_ascii=False, indent=2)

    if os.path.exists(tmp_file):
        os.remove(tmp_file)

    print(f"\n{'='*50}")
    print(f"完成！共抓取 {len(all_comments)} 条评论")
    print(f"保存到: {out_file}")


if __name__ == "__main__":
    main()
