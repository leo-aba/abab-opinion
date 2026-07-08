"""清洗评论向量化脚本

从 test/ 目录加载清洗后的评论 JSON 文件，使用本地 Qwen3-Embedding
模型进行向量化，输出保存到 data/vector/comment_vectors.npy。

用法:
    python test/embed_comments.py
    python test/embed_comments.py --batch-size 32

依赖:
    pip install sentence-transformers numpy
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

# ── 路径 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 嵌入模型实际位置（sentence-transformers 格式）
MODEL_PATH = (
    PROJECT_ROOT
    / "backend" / "models" / "embedding"
    / "embedding" / "models--Qwen--Qwen3-Embedding-0.6B"
    / "snapshots" / "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
)

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "data" / "vector"

# test/ 目录下清洗后的评论 JSON 文件（匹配 *_cleaned.json）
TEST_DIR = PROJECT_ROOT / "test"


def discover_cleaned_files() -> list[Path]:
    """扫描 test/ 下所有清洗后的 JSON 文件"""
    pattern = "*_cleaned.json"
    files = sorted(TEST_DIR.glob(pattern))
    if not files:
        print(f"[错误] 未找到匹配 {pattern} 的文件，请确认 test/ 目录下存在清洗后的 JSON。")
        sys.exit(1)
    return files


def load_comments(file_paths: list[Path]) -> list[str]:
    """从多个 JSON 文件加载所有评论 text"""
    all_texts: list[str] = []
    source_map: list[tuple[str, int, str]] = []  # (filename, index_in_file, text)

    for fp in file_paths:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for i, item in enumerate(data):
                text = item.get("text", "")
                if text and text.strip():
                    all_texts.append(text.strip())
                    source_map.append((fp.name, i, text.strip()))
        else:
            print(f"[警告] 跳过非列表格式: {fp.name}")
    return all_texts, source_map


def main():
    parser = argparse.ArgumentParser(description="清洗评论向量化")
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="编码批大小（默认 32，按显存调整）",
    )
    parser.add_argument(
        "--show-progress", action="store_true", default=True,
        help="显示进度条",
    )
    args = parser.parse_args()

    # 1) 发现评论文件
    files = discover_cleaned_files()
    print(f"发现 {len(files)} 个清洗文件:")
    for f in files:
        print(f"  - {f.name}")

    # 2) 加载评论
    print("\n正在加载评论...")
    texts, source_map = load_comments(files)
    print(f"共加载 {len(texts)} 条有效评论")

    if len(texts) == 0:
        print("[错误] 没有找到有效评论文本。")
        sys.exit(1)

    # 3) 加载模型
    print(f"\n正在加载嵌入模型...")
    print(f"模型路径: {MODEL_PATH}")
    t0 = time.time()

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("[错误] 请先安装 sentence-transformers: pip install sentence-transformers")
        sys.exit(1)

    if not MODEL_PATH.exists():
        print(f"[错误] 模型路径不存在: {MODEL_PATH}")
        print("请确认模型已下载到正确位置。")
        sys.exit(1)

    model = SentenceTransformer(str(MODEL_PATH))
    print(f"模型加载完成，耗时 {time.time() - t0:.1f}s")
    print(f"向量维度: {model.get_sentence_embedding_dimension()}")

    # 4) 编码（分批）
    print(f"\n正在向量化 {len(texts)} 条评论（批大小={args.batch_size}）...")
    t1 = time.time()

    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=args.show_progress,
        normalize_embeddings=True,  # L2 归一化，方便后续余弦相似度计算
    )

    elapsed = time.time() - t1
    print(f"向量化完成，耗时 {elapsed:.1f}s ({len(texts)/elapsed:.0f} 条/秒)")
    print(f"向量形状: {embeddings.shape}")

    # 5) 保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    npy_path = OUTPUT_DIR / "comment_vectors.npy"
    np.save(str(npy_path), embeddings)
    print(f"\n向量已保存: {npy_path}")

    # 可选：保存一条 source map 方便追溯
    map_path = OUTPUT_DIR / "comment_source_map.json"
    source_info = [
        {"file": s[0], "index": s[1], "text_preview": s[2][:80]}
        for s in source_map
    ]
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(source_info, f, ensure_ascii=False, indent=2)
    print(f"来源映射已保存: {map_path}")

    # 6) 简单统计
    print("\n" + "=" * 50)
    print(f"总计向量化评论: {len(texts)}")
    print(f"向量维度:       {embeddings.shape[1]}")
    print(f"内存占用:       {embeddings.nbytes / 1024 / 1024:.1f} MB")
    print("=" * 50)


if __name__ == "__main__":
    main()
