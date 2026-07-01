from sentence_transformers import SentenceTransformer
import config

model = SentenceTransformer(
    str(config.EMBEDDING_LOCAL_PATH),
    device=config.DEVICE
)

text = "这部电影剧情很棒，演员演技在线"

embedding = model.encode(text)

print(embedding.shape)
print(embedding[:10])