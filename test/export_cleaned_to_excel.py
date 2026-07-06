"""清洗后评论 → Excel 导出
从 test/ 下所有 *_cleaned.json 文件导出为结构化 Excel

用法：python test/export_cleaned_to_excel.py
输出：test/cleaned_comments.xlsx
"""

import sys, os, json, re
from datetime import datetime
from openpyxl import Workbook

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 从文件名中提取 video_id，如 douyin_comments_7649393137122577716_cleaned.json
RE_VIDEO_ID = re.compile(r'douyin_comments_(\d+)_cleaned\.json$')


def main():
    # 查找所有清洗后的文件
    cleaned_files = [
        os.path.join(TEST_DIR, f)
        for f in os.listdir(TEST_DIR)
        if RE_VIDEO_ID.match(f)
    ]

    if not cleaned_files:
        print("未找到任何 *_cleaned.json 文件")
        return

    print(f"找到 {len(cleaned_files)} 个清洗后文件")

    wb = Workbook()
    ws = wb.active
    ws.title = "清洗评论"

    # 表头
    headers = ['cid', 'text', 'video_id', 'platform', 'cleaned_time']
    ws.append(headers)
    # 列宽
    ws.column_dimensions['A'].width = 22   # cid
    ws.column_dimensions['B'].width = 80   # text
    ws.column_dimensions['C'].width = 24   # video_id
    ws.column_dimensions['D'].width = 12   # platform
    ws.column_dimensions['E'].width = 22   # cleaned_time

    total_rows = 0

    for fp in sorted(cleaned_files):
        fname = os.path.basename(fp)
        match = RE_VIDEO_ID.search(fname)
        video_id = match.group(1)

        with open(fp, 'r', encoding='utf-8') as f:
            comments = json.load(f)

        if not isinstance(comments, list):
            print(f"  跳过 {fname}：格式不是列表")
            continue

        for c in comments:
            ws.append([
                c.get('cid', ''),
                c.get('text', ''),
                video_id,
                'douyin',
                NOW,
            ])

        print(f"  {fname} → 导出 {len(comments)} 条 (video_id={video_id})")
        total_rows += len(comments)

    # 输出路径
    out_path = os.path.join(TEST_DIR, 'cleaned_comments.xlsx')
    wb.save(out_path)

    print(f"\n{'='*50}")
    print(f"导出完成！共 {total_rows} 条评论")
    print(f"保存到: {out_path}")


if __name__ == '__main__':
    main()
