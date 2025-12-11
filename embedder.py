# embedder.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL = "text-embedding-3-large"

def embed_texts(texts: list):
    """
    texts: List[str]
    returns: List[List[float]] embeddings
    """
    embeddings = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        sub = texts[i:i+batch_size]
        resp = client.embeddings.create(
            model=EMBED_MODEL,
            input=sub
        )
        embeddings.extend([item.embedding for item in resp.data])
    return embeddings
