import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


def get_llm():
    """
    Returns a configured LLM instance based on the LLM_PROVIDER
    environment variable. Currently supports Google Gemini.
    Designed to be swapped out for other LangChain-compatible LLMs.
    """
    provider = os.getenv("LLM_PROVIDER", "google").lower()

    if provider == "google":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set in .env")
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: '{provider}'")
