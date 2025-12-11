# chunker.py
import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")

def chunk_text_by_tokens(text: str, max_tokens: int = 400, overlap: int = 50):
    tokens = ENC.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk = ENC.decode(tokens[start:end])
        chunks.append(chunk)
        if end == len(tokens):
            break
        start = end - overlap
    return chunks
