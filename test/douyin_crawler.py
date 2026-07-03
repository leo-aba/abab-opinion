"""抖音评论爬虫 — 使用 Selenium + JS fetch 绕过反爬
用法：修改下面的 aweme_id，然后运行即可
"""
import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# ========== 配置区 ==========
AWEME_ID = "7649393137122577716"  # 视频ID（19位数字）
MAX_PAGES = 50                    # 最多抓取页数（每页20条）
SLEEP_SEC = 1.5                   # 翻页间隔（秒）
# ============================


def create_driver():
    """创建 Selenium Chrome Driver（含反检测配置）"""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    d = webdriver.Chrome(options=options)
    d.set_script_timeout(15)
    return d


def js_fetch_comments(driver, aweme_id, cursor=0, count=20):
    """通过 JS fetch 从浏览器内部调用抖音评论API"""
    js = """
    var aweme_id = arguments[0], cursor = arguments[1], count = arguments[2];
    var callback = arguments[arguments.length - 1];
    var url = "https://www.douyin.com/aweme/v1/web/comment/list/?aweme_id=" + aweme_id
        + "&cursor=" + cursor + "&count=" + count + "&device_platform=webapp";
    fetch(url, {
        credentials: "include",
        headers: {"Accept": "application/json"}
    }).then(function(r) { return r.json(); }).then(function(d) {
        callback(JSON.stringify({
            status_code: d.status_code,
            total: d.total,
            has_more: d.has_more,
            cursor: d.cursor,
            comments: d.comments || []
        }));
    }).catch(function(e) {
        callback(JSON.stringify({error: e.message}));
    });
    """
    result = driver.execute_async_script(js, aweme_id, cursor, count)
    return json.loads(result)


def extract_comment_info(c):
    """提取评论中的关键字段"""
    return {
        "cid": c.get("cid", ""),
        "text": c.get("text", ""),
        "create_time": c.get("create_time", 0),
        "digg_count": c.get("digg_count", 0),
        "reply_comment_total": c.get("reply_comment_total", 0),
        "user": {
            "uid": c.get("user", {}).get("uid", ""),
            "nickname": c.get("user", {}).get("nickname", ""),
            "sec_uid": c.get("user", {}).get("sec_uid", ""),
        },
        "is_hot": c.get("is_hot", False),
    }


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_file = os.path.join(out_dir, f"douyin_comments_{AWEME_ID}.json")
    tmp_file = os.path.join(out_dir, f"douyin_comments_{AWEME_ID}_tmp.json")

    driver = create_driver()
    try:
        # 1. 访问抖音首页获取 Cookie
        print("1. 初始化浏览器...")
        driver.get("https://www.douyin.com/")
        time.sleep(5)
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        print(f"   Cookie数: {len(cookies)}, __ac_signature: {'__ac_signature' in cookies}")

        # 2. 如果 ID 是 note 类型，先访问 note 页面
        url = f"https://www.douyin.com/video/{AWEME_ID}"
        print(f"2. 访问视频页面: {url}")
        driver.get(url)
        time.sleep(5)

        # 3. 循环抓取评论
        all_comments = []
        cursor = 0
        page = 0
        has_more = True

        print(f"3. 开始抓取评论 (最多 {MAX_PAGES} 页)...")
        while has_more and page < MAX_PAGES:
            page += 1
            print(f"\n   第 {page} 页 (cursor={cursor})...", end=" ", flush=True)

            data = js_fetch_comments(driver, AWEME_ID, cursor=cursor, count=20)

            if "error" in data:
                print(f"API错误: {data['error']}")
                break

            print(f"status={data.get('status_code')}, ", end="", flush=True)

            comments = data.get("comments", [])
            if not comments:
                print("无更多评论")
                break

            # 提取并保存评论
            for c in comments:
                all_comments.append(extract_comment_info(c))

            print(f"累计 {len(all_comments)}/{data.get('total', '?')} 条", end="", flush=True)

            # 更新翻页状态
            has_more = data.get("has_more", False)
            cursor = data.get("cursor", 0)

            # 每10页保存一次临时结果
            if page % 10 == 0:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(all_comments, f, ensure_ascii=False, indent=2)
                print(f" [已保存临时文件]", end="", flush=True)

            print()
            time.sleep(SLEEP_SEC)

        # 4. 保存最终结果
        print(f"\n4. 保存结果 ({len(all_comments)} 条评论)...")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(all_comments, f, ensure_ascii=False, indent=2)

        # 清理临时文件
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

        print(f"\n{'='*50}")
        print(f"完成！共抓取 {len(all_comments)} 条评论")
        print(f"保存到: {out_file}")
        print(f"{'='*50}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
