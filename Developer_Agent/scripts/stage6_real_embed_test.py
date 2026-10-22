from app.rag.embeddings import get_embeddings

emb = get_embeddings()
vec = emb.embed_query("user login with password")
print("Embedding length:", len(vec))
print("First 3 numbers:", vec[:3])