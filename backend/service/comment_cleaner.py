"""评论清洗服务 — 过滤无意义评论（纯表情、纯标点、占位等）

从 test/clean_comments.py 提取核心清洗逻辑，供分析流程调用。
"""

import re
import logging

logger = logging.getLogger("comment_cleaner")

# ========== Unicode 范围 ==========
RE_CHINESE = re.compile(r'[一-鿿㐀-䶿豈-﫿]')
RE_PUNCTUATION = re.compile(r'[　-〿＀-￯\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]')
RE_EMOJI = re.compile(
    '[\U0001F600-\U0001F64F'
    '\U0001F300-\U0001F5FF'
    '\U0001F680-\U0001F6FF'
    '\U0001F1E0-\U0001F1FF'
    '\U00002702-\U000027B0'
    '\U0001F900-\U0001F9FF'
    '\U0001FA00-\U0001FA6F'
    '\U0001FA70-\U0001FAFF'
    '\U00002600-\U000026FF'
    '\U0000FE00-\U0000FE0F'
    '\U0000200D'
    '\U000000A9\U000000AE'
    '\U0000203C\U00002049'
    '\U00002122'
    '\U00002139'
    '\U00002194-\U00002199'
    '\U000021A9-\U000021AA'
    '\U00002300-\U000023FF'
    '\U000024C2'
    '\U000025AA-\U000025FE'
    '\U00002934-\U00002935'
    '\U00002B05-\U00002B55'
    '\U00003030-\U0000303D'
    '\U00003297-\U00003299'
    ']', flags=re.UNICODE
)
RE_REPEATED_CHAR = re.compile(r'^(.)\1{4,}$')
RE_ONLY_NUMBERS = re.compile(r'^\d{1,3}$')
RE_ONLY_LETTERS = re.compile(r'^[a-zA-Z]{1,5}$')
RE_DOUYIN_EMOJI = re.compile(r'\[[^\[\]]+\]')
RE_AT_MENTION = re.compile(r'@\S+')
MEANINGLESS_PHRASES = {'前排', '沙发'}
RE_MEANINGLESS_PATTERN = re.compile(r'^(来了\s*)+$')


def has_meaningful_text(text: str) -> bool:
    """判断评论是否有有意义的文字"""
    if not text or not text.strip():
        return False

    no_at = RE_AT_MENTION.sub('', text.strip()).strip()

    # 去掉@后空了 → 纯@别人
    if not no_at:
        return False

    # 去掉@后只剩下抖音表情 [xxx]
    if RE_DOUYIN_EMOJI.sub('', no_at).strip() == '':
        return False

    # 无意义占位评论
    if no_at in MEANINGLESS_PHRASES:
        return False

    # 去掉表情符号后剩下的部分
    no_emoji = RE_EMOJI.sub('', no_at).strip()
    no_punct = RE_PUNCTUATION.sub('', no_emoji).strip()

    # 去完表情和标点后空了 → 纯表情/纯标点
    if not no_punct:
        return False

    # 只有1-3位数字
    if RE_ONLY_NUMBERS.match(no_punct):
        return False

    # 只有1-5个英文字母
    if RE_ONLY_LETTERS.match(no_punct):
        return False

    # "来了"、"来了来了"等无意义评论
    if RE_MEANINGLESS_PATTERN.match(no_punct):
        return False

    # 同一个字符重复5次以上（保留中文重复如"哈哈哈"）
    if RE_REPEATED_CHAR.match(no_at):
        if not RE_CHINESE.search(no_at):
            return False

    # 中文字数少于2个且没有其他有意义的内容
    chinese_chars = RE_CHINESE.findall(no_punct)
    if len(chinese_chars) == 0:
        if len(no_punct) < 2:
            return False
    elif len(chinese_chars) == 1 and len(no_punct) <= 2:
        return False

    return True


def clean_comment(comment: dict) -> dict | None:
    """清洗单条评论，返回完整评论 dict 或 None（需过滤）"""
    text = comment.get('text', '')
    text = text.strip() if text else ''

    if not text:
        return None

    if not has_meaningful_text(text):
        return None

    return comment


def clean_comments(raw_comments: list[dict]) -> tuple[list[dict], dict]:
    """批量清洗评论。

    Args:
        raw_comments: 原始评论列表，每条包含 text 等字段

    Returns:
        (cleaned, stats): 清洗后的评论列表 + 统计信息
            stats = {
                "total": int,        # 原始总数
                "kept": int,         # 保留数
                "removed": int,      # 去除总数
                "removed_empty": int,      # 空评论
                "removed_emoji": int,      # 纯表情
                "removed_meaningless": int, # 其他无意义
            }
    """
    total = len(raw_comments)
    cleaned: list[dict] = []
    removed_empty = 0
    removed_emoji = 0
    removed_meaningless = 0

    for c in raw_comments:
        text = c.get('text', '').strip() if c.get('text') else ''

        if not text:
            removed_empty += 1
            continue

        if not has_meaningful_text(text):
            # 判断是纯表情还是其他无意义
            no_at = RE_AT_MENTION.sub('', text).strip()
            no_emoji = RE_EMOJI.sub('', no_at).strip()
            no_punct = RE_PUNCTUATION.sub('', no_emoji).strip()
            if no_at and not no_punct:
                removed_emoji += 1
            else:
                removed_meaningless += 1
            continue

        cleaned.append(c)

    removed = removed_empty + removed_emoji + removed_meaningless
    stats = {
        "total": total,
        "kept": len(cleaned),
        "removed": removed,
        "removed_empty": removed_empty,
        "removed_emoji": removed_emoji,
        "removed_meaningless": removed_meaningless,
    }

    logger.info(
        "评论清洗完成: 原始=%d, 保留=%d, 去除=%d (空=%d, 表情=%d, 无意义=%d)",
        total, len(cleaned), removed,
        removed_empty, removed_emoji, removed_meaningless,
    )

    return cleaned, stats
