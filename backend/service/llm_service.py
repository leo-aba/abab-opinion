"""LLM 服务 — 调用 DeepSeek 进行评论分析（话题分类、情感、综述）"""

import json
import logging
from openai import AsyncOpenAI

from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger("llm_service")


def _build_analysis_prompt(comments: list[dict]) -> str:
    """构造发给 LLM 的分析 prompt，要求返回结构化 JSON。

    每条评论编号为 0..N-1，LLM 通过 comment_indices 指回具体评论。
    """
    # 格式化评论为带编号的文本
    comment_lines = []
    for i, c in enumerate(comments):
        text = c.get("text", "").strip()
        if not text:
            continue
        # 限制单条评论最长 300 字，避免个别超长评论撑爆 prompt
        if len(text) > 300:
            text = text[:300] + "..."
        comment_lines.append(f"评论{i}：{text}")

    comments_text = "\n".join(comment_lines)

    prompt = f"""你是一个专业的评论分析助手。下面是一批用户评论，每条评论带有编号（评论0, 评论1, ...）。

请你完成以下任务，并以 JSON 格式返回结果：

1. **话题分类**：将所有评论归纳为若干个话题类别（不超过 8 个），每个话题包含：
   - name: 话题名称（简短的，如"产品价格讨论"）
   - keywords: 该话题的 3-5 个关键词
   - comment_indices: 属于该话题的评论编号列表（整数数组，如 [0, 3, 5]）
   - summary: 该话题的观点总结（100-200字）
   - sentiment: 该话题的情感分布，格式为 {{"positive": N, "negative": N, "neutral": N}}

2. **属性情感分析**：根据评论内容，归纳 4-6 个评价维度（aspect），每个维度统计正/负/中性评论数。例如游戏视频可归纳"画质""玩法""难度""配音""剧情"等，根据实际内容灵活命名。每个维度包含：
   - name: 维度名称（如"画质"）
   - positive: 正面评价的评论数
   - negative: 负面评价的评论数
   - neutral: 中性评价的评论数
   （一条评论可同时涉及多个维度，各维度评论数之和可能超过总评论数）

3. **整体综述**：一段 200-400 字的综合综述，概括整体舆论倾向、主要观点分歧、用户情绪等。

要求：
- 每条评论必须归属到某一个话题（不能遗漏、不能重复归属）
- 情感判断标准：positive=正面/赞美/支持，negative=负面/批评/反对，neutral=中性/客观/疑问
- 话题数量不要超过 8 个，如果评论本身少（<20条），话题数量相应减少
- 属性维度命名要具体、贴近内容，不要用笼统的词（如"整体评价"）
- 整体综述要客观、全面，既有正面也有负面

评论列表：
{comments_text}

请严格按以下 JSON 格式返回（只返回 JSON，不要附加其他文字）：
```json
{{
  "topics": [
    {{
      "name": "话题名称",
      "keywords": ["关键词1", "关键词2", "关键词3"],
      "comment_indices": [0, 1, 2],
      "summary": "该话题的观点总结",
      "sentiment": {{"positive": 10, "negative": 5, "neutral": 3}}
    }}
  ],
  "aspects": [
    {{
      "name": "评价维度名",
      "positive": 30,
      "negative": 5,
      "neutral": 10
    }}
  ],
  "overall_summary": "整体综述内容"
}}
```"""
    return prompt


async def analyze_comments_with_llm(comments: list[dict]) -> dict:
    """调用 DeepSeek 大模型分析评论。

    Args:
        comments: 评论列表，每项 dict 至少包含 "text" 字段。
                  评论按列表顺序编号 0..N-1，LLM 返回 comment_indices 来关联。

    Returns:
        dict: {"topics": [...], "aspects": [...], "overall_summary": "..."}
              失败时返回 {"topics": [], "aspects": [], "overall_summary": ""}
    """
    if not comments:
        logger.warning("评论列表为空，跳过 LLM 分析")
        return {"topics": [], "aspects": [], "overall_summary": ""}

    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY 未配置，跳过 LLM 分析")
        return {"topics": [], "aspects": [], "overall_summary": ""}

    logger.info("开始 LLM 分析: 评论数=%d, model=%s", len(comments), DEEPSEEK_MODEL)

    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )

    prompt = _build_analysis_prompt(comments)

    try:
        resp = await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的评论分析助手。请严格按 JSON 格式返回结果，不要附加任何其他文字。"
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            timeout=300,  # 5 分钟超时
        )

        raw = resp.choices[0].message.content
        logger.info("LLM 响应长度: %d 字符", len(raw) if raw else 0)

        # 解析 JSON
        result = json.loads(raw)
        topics = result.get("topics", [])
        aspects = result.get("aspects", [])
        overall_summary = result.get("overall_summary", "")

        logger.info(
            "LLM 分析完成: 话题数=%d, 属性维数=%d, 综述长度=%d",
            len(topics), len(aspects), len(overall_summary),
        )
        return {"topics": topics, "aspects": aspects, "overall_summary": overall_summary}

    except json.JSONDecodeError as e:
        logger.error("LLM 返回 JSON 解析失败: %s", e)
        return {"topics": [], "aspects": [], "overall_summary": ""}
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        return {"topics": [], "aspects": [], "overall_summary": ""}


# ──────────────────────────────────────────────
# 增量分类（用于实时追踪模式）
# ──────────────────────────────────────────────


def _build_incremental_classification_prompt(
    new_comments: list[dict],
    existing_topics: list[dict],
) -> str:
    """构造增量分类 prompt：将新评论归入已有话题并判断逐条情感。

    每条新评论编号 0..N-1，LLM 返回 assignments 数组。
    """
    # 格式化已有话题
    topic_lines = []
    for t in existing_topics:
        name = t.get("name", "")
        keywords = t.get("keywords", [])
        if isinstance(keywords, list):
            kw_str = "、".join(keywords)
        else:
            kw_str = str(keywords)
        topic_lines.append(f'- "{name}" [关键词: {kw_str}]')

    topics_text = "\n".join(topic_lines) if topic_lines else "（暂无已有话题）"

    # 格式化新评论
    comment_lines = []
    for i, c in enumerate(new_comments):
        text = c.get("text", "").strip()
        if not text:
            continue
        if len(text) > 200:
            text = text[:200] + "..."
        comment_lines.append(f"评论{i}：{text}")

    comments_text = "\n".join(comment_lines)

    prompt = f"""你是一个评论分类助手。以下是已有的评论话题分类和一批新评论。

已有话题：
{topics_text}

新评论：
{comments_text}

请将每条新评论分类到最匹配的已有话题中，并判断每条评论的情感倾向。
- 如果评论不属于任何已有话题，请将其归入"其他"
- 情感判断标准：positive=正面/赞美/支持，negative=负面/批评/反对，neutral=中性/客观/疑问
- 每条评论必须恰好有一个分类结果

请严格按以下 JSON 格式返回（只返回 JSON）：
```json
{{
  "assignments": [
    {{"comment_index": 0, "topic_name": "话题名称", "sentiment": "positive"}},
    {{"comment_index": 1, "topic_name": "其他", "sentiment": "neutral"}}
  ]
}}
```"""
    return prompt


async def classify_new_comments_with_llm(
    new_comments: list[dict],
    existing_topics: list[dict],
) -> dict:
    """增量分类：将新评论归入已有话题并判断逐条情感。

    Args:
        new_comments: 新评论列表，每项至少含 "text" 字段
        existing_topics: 已有话题列表，每项含 "name"、"keywords"

    Returns:
        dict: {{"assignments": [{{"comment_index": 0, "topic_name": "...", "sentiment": "positive"}}, ...]}}
              失败时返回 {{"assignments": []}}
    """
    if not new_comments:
        return {"assignments": []}

    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY 未配置，跳过增量分类")
        return {"assignments": []}

    logger.info("开始增量分类: 新评论=%d, 已有话题=%d", len(new_comments), len(existing_topics))

    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )

    prompt = _build_incremental_classification_prompt(new_comments, existing_topics)

    try:
        resp = await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的评论分类助手。请严格按 JSON 格式返回结果，不要附加任何其他文字。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,  # 低温度确保分类一致性
            response_format={"type": "json_object"},
            timeout=120,  # 增量分类较快，2 分钟足够
        )

        raw = resp.choices[0].message.content
        logger.info("增量分类 LLM 响应长度: %d 字符", len(raw) if raw else 0)

        result = json.loads(raw)
        assignments = result.get("assignments", [])

        logger.info("增量分类完成: %d 条分配结果", len(assignments))
        return {"assignments": assignments}

    except json.JSONDecodeError as e:
        logger.error("增量分类 JSON 解析失败: %s", e)
        return {"assignments": []}
    except Exception as e:
        logger.error("增量分类 LLM 调用失败: %s", e)
        return {"assignments": []}
