from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import GOOGLE_API_KEY, MODEL_NAME


def get_llm(temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    """Create and return a configured Gemini model."""
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=GOOGLE_API_KEY,
        temperature=temperature,
    )