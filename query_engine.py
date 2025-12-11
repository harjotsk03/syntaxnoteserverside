# query_engine.py
import os
from supabase_client import supabase
import openai
from neo4j_client import driver
from dotenv import load_dotenv
import numpy as np
from embedder import client, EMBED_MODEL

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

CHAT_MODEL = "gpt-4.1"

def embed_query(text: str):
    resp = client.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding

# For chat completion
def ask_chat(prompt: str):
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800
    )
    return resp.choices[0].message.content

def search_chunks(repo_id: str, query: str, k=5, fetch_multiplier=3):
    q_emb = embed_query(query)
    
    with driver.session() as session:
        result = session.run("""
            MATCH (r:Repo {id: $repo_id})-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.file_path AS file_path, c.chunk_index AS chunk_index,
                   c.content AS content, c.embedding AS embedding
        """, repo_id=repo_id)

        chunks = []
        for r in result:
            emb = np.array(r["embedding"], dtype=float)
            chunks.append({
                "file_path": r["file_path"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "embedding": emb
            })

    q_vec = np.array(q_emb)
    for c in chunks:
        c["score"] = np.dot(q_vec, c["embedding"]) / (
            np.linalg.norm(q_vec) * np.linalg.norm(c["embedding"])
        )

    # Fetch more initially, then diversify
    top_chunks = sorted(chunks, key=lambda x: x["score"], reverse=True)[: k * fetch_multiplier]
    
    # Diversify: ensure we get chunks from different files
    selected = []
    seen_files = set()
    
    for chunk in top_chunks:
        if len(selected) >= k:
            break
        if chunk["file_path"] not in seen_files:
            selected.append(chunk)
            seen_files.add(chunk["file_path"])
    
    # Fill remaining slots if needed
    for chunk in top_chunks:
        if len(selected) >= k:
            break
        if chunk not in selected:
            selected.append(chunk)
    
    return selected[:k]

def get_graph_context(repo_id: str, paths: list):
    # find neighbors for each top chunk file_path
    neighbors = {}
    with driver.session() as session:
        for p in paths:
            result = session.run("""
                MATCH (f:File {repo_id:$repo_id, path:$path})-[:DEPENDS_ON*1..2]->(n)
                RETURN DISTINCT n.path AS path
            """, repo_id=repo_id, path=p)
            neighbors[p] = [r["path"] for r in result]
    return neighbors

def answer_question(repo_id: str, question: str, top_k=8):
    chunks = search_chunks(repo_id, question, top_k)
    top_paths = list({c["file_path"] for c in chunks})
    graph_ctx = get_graph_context(repo_id, top_paths)

    context_text = "\n\n".join([f"FILE: {c['file_path']}\n\n{c['content']}" for c in chunks])

    prompt = f"""You are an expert code analyst. Analyze the provided code snippets and file dependencies to answer the question.

IMPORTANT INSTRUCTIONS:
- Be specific and cite actual code, file names, and technical details
- If you see specific technologies, frameworks, or libraries, name them explicitly
- Describe the architecture, tech stack, and key features you observe
- Look for routes, API endpoints, database schemas, UI components, etc.
- Be concise but thorough - focus on the most important technical details

CODE CONTEXT:
{context_text}

FILE DEPENDENCIES:
{graph_ctx}

QUESTION: {question}

Provide a detailed, technical answer based on the code provided:"""
    
    resp = ask_chat(prompt)
    return resp
