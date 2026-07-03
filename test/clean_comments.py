"""抖音评论清洗脚本
- 只保留评论ID (cid) 和评论内容 (text)
- 去除纯表情评论（无文字）
- 去除无意义的评论（纯标点、纯空格、乱码等）

用法：python test/clean_comments.py
会自动处理 test/ 下所有 douyin_comments_*.json 文件
"""

import sys, os, json, re

sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== Unicode 范围 ==========
RE_CHINESE = re.compile(r'[一-鿿㐀-䶿豈-﫿]')  # 中文字符
RE_PUNCTUATION = re.compile(r'[　-〿＀-￯\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]')  # 标点符号
RE_EMOJI = re.compile(
    '[\U0001F600-\U0001F64F'   # 表情符号
    '\U0001F300-\U0001F5FF'    # 符号和象形字
    '\U0001F680-\U0001F6FF'    # 交通和地图符号
    '\U0001F1E0-\U0001F1FF'    # 国旗
    '\U00002702-\U000027B0'    # 丁字符号
    '\U0001F900-\U0001F9FF'    # 补充符号和象形字
    '\U0001FA00-\U0001FA6F'    # 象形字扩展A
    '\U0001FA70-\U0001FAFF'    # 象形字扩展B
    '\U00002600-\U000026FF'    # 杂项符号
    '\U0000FE00-\U0000FE0F'    # 变异选择器
    '\U0000200D'               # 零宽连接符
    # 以下范围替代原来的 \U000024C2-\U0001F251（注意不能跨过U+4E00中文区）
    '\U000000A9\U000000AE'     # ©, ®
    '\U0000203C\U00002049'     # ‼, ⁉
    '\U00002122'               # ™
    '\U00002139'               # ℹ
    '\U00002194-\U00002199'    # ↕ 箭头
    '\U000021A9-\U000021AA'    # ↩, ↪
    '\U00002300-\U000023FF'    # 技术符号 (⏩⏪⏫等)
    '\U000024C2'               # Ⓜ
    '\U000025AA-\U000025FE'    # 几何形状 (▪◼◽等)
    '\U00002934-\U00002935'    # ⤴, ⤵
    '\U00002B05-\U00002B55'    # ⭐⭕等
    '\U00003030-\U0000303D'    # 〰, 〽
    '\U00003297-\U00003299'    # ㊗, ㊙
    ']', flags=re.UNICODE
)
RE_REPEATED_CHAR = re.compile(r'^(.)\1{4,}$')  # 重复5次以上同一个字符
RE_ONLY_NUMBERS = re.compile(r'^\d{1,3}$')      # 纯 1-3 位数字
RE_ONLY_LETTERS = re.compile(r'^[a-zA-Z]{1,5}$')  # 纯 1-5 个英文字母
RE_DOUYIN_EMOJI = re.compile(r'\[[^\[\]]+\]')    # 抖音内置表情 [xxx]，如[图片表情]、[看]
RE_AT_MENTION = re.compile(r'@\S+')               # @用户名
MEANINGLESS_PHRASES = {'前排', '沙发'}             # 无意义占位评论
RE_MEANINGLESS_PATTERN = re.compile(r'^(来了\s*)+$')  # "来了"、"来了来了"、"来了 来了"等


def has_meaningful_text(text):
    """判断是否有有意义的文字"""
    if not text or not text.strip():
        return False

    # 去掉空格和@提及
    no_at = RE_AT_MENTION.sub('', text.strip()).strip()

    # 去掉@后空了 → 纯@别人，没发表意见
    if not no_at:
        return False

    # 去掉@后只剩下抖音表情 [xxx] → 纯@+表情
    if RE_DOUYIN_EMOJI.sub('', no_at).strip() == '':
        return False

    # 无意义占位评论（如"前排"、"沙发"）
    if no_at in MEANINGLESS_PHRASES:
        return False

    # 去掉表情符号后剩下的部分（用no_at，排除@干扰）
    no_emoji = RE_EMOJI.sub('', no_at).strip()

    # 去掉标点符号后剩下的部分
    no_punct = RE_PUNCTUATION.sub('', no_emoji).strip()

    # 去完表情和标点后空了 → 纯表情/纯标点
    if not no_punct:
        return False

    # 只有1-3位数字 → 无意义（如 "666" 保留有争议，但先过滤掉）
    if RE_ONLY_NUMBERS.match(no_punct):
        return False

    # 只有1-5个英文字母
    if RE_ONLY_LETTERS.match(no_punct):
        return False

    # "来了"、"来了来了"、"来了 来了"等无意义评论
    if RE_MEANINGLESS_PATTERN.match(no_punct):
        return False

    # 同一个字符重复5次以上（如 "。。。。。"、"xxxxx"）
    if RE_REPEATED_CHAR.match(no_at):
        # 但保留有意义的重复，如 "哈哈哈"、"呜呜呜"等中文重复
        if not RE_CHINESE.search(no_at):
            return False

    # 中文字数少于2个且没有其他有意义的内容
    chinese_chars = RE_CHINESE.findall(no_punct)
    if len(chinese_chars) == 0:
        # 没有中文 → 检查剩余文本长度
        if len(no_punct) < 2:
            return False
    elif len(chinese_chars) == 1 and len(no_punct) <= 2:
        # 只有1个中文字 + 可能1个标点 → 无意义
        return False

    return True


def clean_comment(comment):
    """清洗单条评论，返回 {'cid': ..., 'text': ...} 或 None（需过滤）"""
    cid = comment.get('cid', '')
    text = comment.get('text', '')

    if not cid:
        return None

    text = text.strip()
    if not text:
        return None

    # 检查是否有意义
    if not has_meaningful_text(text):
        return None

    return {'cid': cid, 'text': text}


def process_file(input_path):
    """处理单个 JSON 文件"""
    print(f"\n处理文件: {os.path.basename(input_path)}")

    with open(input_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    if not isinstance(raw_data, list):
        print(f"  跳过：文件格式不是列表")
        return

    total = len(raw_data)
    print(f"  原始评论数: {total}")

    cleaned = []
    removed = {'emoji_only': 0, 'empty': 0, 'meaningless': 0}

    for comment in raw_data:
        result = clean_comment(comment)

        if result is None:
            text = comment.get('text', '').strip()
            if not text:
                removed['empty'] += 1
            elif not has_meaningful_text(text):
                # 判断是纯表情还是其他无意义
                if text and RE_EMOJI.sub('', text).strip() == '':
                    removed['emoji_only'] += 1
                else:
                    removed['meaningless'] += 1
            continue

        cleaned.append(result)

    # 输出统计
    print(f"  清洗后: {len(cleaned)} 条")
    print(f"  去除详情: 空评论={removed['empty']}, 纯表情={removed['emoji_only']}, 其他无意义={removed['meaningless']}")

    # 保存
    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_cleaned{ext}"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"  保存到: {os.path.basename(output_path)} ({len(cleaned)} 条)")
    return cleaned


def main():
    # 查找所有 douyin_comments_*.json 文件（排除已清洗的）
    pattern = re.compile(r'douyin_comments_\d+\.json$')
    files = [
        os.path.join(TEST_DIR, f)
        for f in os.listdir(TEST_DIR)
        if pattern.match(f) and not f.endswith('_cleaned.json')
    ]

    if not files:
        print("未找到 douyin_comments_*.json 文件")
        return

    print(f"找到 {len(files)} 个文件待清洗")
    total_before = 0
    total_after = 0

    for fp in sorted(files):
        result = process_file(fp)
        if result:
            total_before += len(result)  # 实际是原始数量在 process_file 里
            total_after += len(result)

    print(f"\n{'='*50}")
    print("清洗完成！")


if __name__ == '__main__':
    main()
