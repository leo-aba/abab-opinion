import json

def extract_all_comments(file_path):
    comment_texts = []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 遍历数组里每一条一级评论
    for item in data:
        # 提取主评论
        main_msg = item["content"]["message"]
        comment_texts.append(main_msg)

        # 递归解析所有楼中楼回复
        def parse_replies(replies_list):
            if not replies_list:
                return
            for reply in replies_list:
                text = reply["content"]["message"]
                comment_texts.append(text)
                # 深层嵌套回复继续解析
                if reply.get("replies") and len(reply["replies"]) > 0:
                    parse_replies(reply["replies"])

        parse_replies(item.get("replies"))
    return comment_texts


if __name__ == "__main__":
    file = r"E:\pycharm\ababOpinion\test\b站一级评论.json"
    comments = extract_all_comments(file)

    # 控制台打印
    for idx, text in enumerate(comments, 1):
        print(f"{idx}. {text}")

    # 导出纯文本
    out_path = r"E:\pycharm\ababOpinion\test\纯评论文本.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        for txt in comments:
            f.write(txt + "\n")
    print(f"\n提取完成，共{len(comments)}条评论，已保存至：{out_path}")