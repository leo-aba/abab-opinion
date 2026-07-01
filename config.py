from pathlib import Path
import os
import torch

# ===================================
# 项目根目录
# ===================================

BASE_DIR = Path(__file__).parent

# ===================================
# Data
# ===================================

DATA_DIR = BASE_DIR / "data"

RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
VECTOR_DIR = DATA_DIR / "vector"
CLUSTER_DIR = DATA_DIR / "cluster"
SENTIMENT_DIR = DATA_DIR / "sentiment"
TREND_DIR = DATA_DIR / "trend"
SUMMARY_DIR = DATA_DIR / "summary"

RAW_COMMENT_PATH = RAW_DIR / "comments.csv"
CLEAN_COMMENT_PATH = CLEAN_DIR / "clean_comments.csv"
VECTOR_PATH = VECTOR_DIR / "comment_vectors.npy"
TOPIC_COMMENT_PATH = CLUSTER_DIR / "topic_comments.csv"
TOPIC_META_PATH = CLUSTER_DIR / "topic_meta.json"
ASPECT_SENTIMENT_PATH = SENTIMENT_DIR / "aspect_sentiment.csv"
TREND_PATH = TREND_DIR / "daily_topic_trend.csv"

# ===================================
# Model
# ===================================

MODEL_DIR = BASE_DIR / "models"

EMBEDDING_DIR = (
    MODEL_DIR
    / "embedding"
    / "models--Qwen--Qwen3-Embedding-0.6B"
)

SNAPSHOT_DIR = EMBEDDING_DIR / "snapshots"

# 自动找到snapshot目录
snapshot_dirs = [x for x in SNAPSHOT_DIR.iterdir() if x.is_dir()]

if len(snapshot_dirs) == 0:
    raise RuntimeError("没有找到Embedding模型！")

EMBEDDING_LOCAL_PATH = snapshot_dirs[0]

# ===================================
# Device
# ===================================

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ===================================
# API Key（后续Topic命名、总结使用）
# ===================================

DEEPSEEK_API_KEY = ""
QWEN_API_KEY = ""

# ===================================
# Cache
# ===================================

CACHE_DIR = MODEL_DIR / ".hf_cache"

os.environ["HF_HOME"] = str(CACHE_DIR)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

print("=" * 50)
print("当前设备：", DEVICE)
print("Embedding模型：", EMBEDDING_LOCAL_PATH)
print("=" * 50)