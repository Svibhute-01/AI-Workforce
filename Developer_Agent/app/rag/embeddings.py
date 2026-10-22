from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import GOOGLE_API_KEY, EMBEDDING_MODEL


def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )