import os
from openai import OpenAI

# 1. 加载DeepSeek密钥
ds_key = os.getenv("DEEPSEEK_API_KEY")
if not ds_key:
    raise Exception("未配置DeepSeek API环境变量，请先设置DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=ds_key,
    base_url="https://api.deepseek.com"
)

# 2. 读取评论文本文件
txt_path = r"/test/纯评论文本.txt"
with open(txt_path, "r", encoding="utf-8") as f:
    comment_lines = [line.strip() for line in f.readlines() if line.strip()]

# 拼接所有评论为文本块
all_comment_text = "\n".join([f"评论{i+1}：{c}" for i, c in enumerate(comment_lines)])

# 3. 构造提示词：分类所有评论 + 最后输出综述
prompt = f"""
下面是一批评论，你需要完成两件事：
1. 给每一条评论划分观点类别（类别不要过多，最多6类），逐条输出【分类名称】+ 原评论内容；
2. 全部评论分类完成后，单独生成一段完整综合综述：概括网友整体主流看法、情绪倾向、高频讨论点、正反观点。

所有评论内容：
{all_comment_text}

输出格式要求：
---分类评论列表---
【类别1】评论内容1
【类别1】评论内容2
【类别2】评论内容3
……
---综合观点综述---
这里写完整综述
"""

# 调用DeepSeek
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7
)

result = resp.choices[0].message.content

# 打印结果
print("===== 评论分类与综述结果 =====")
print(result)

# 可选：把分类+综述保存到本地结果文件
output_file = r"/test/评论分类综述结果.txt"
with open(output_file, "w", encoding="utf-8") as out_f:
    out_f.write(result)
print(f"\n结果已保存至：{output_file}")