"""Lightweight local RAG for WildNest AI.

Retrieves relevant species care-reference chunks (from rag/documents/) to ground
and cite answers with real sources. Uses Gemini's embedding API for vectors and
pure-Python cosine similarity for retrieval — no heavy ML frameworks needed.
Any failure degrades silently to "no reference material available".
"""
import os
import re
import json
import math

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(_BASE_DIR, 'rag', 'documents')
CACHE_PATH = os.path.join(_BASE_DIR, 'rag', 'embeddings_cache.json')
EMBED_MODEL = 'models/text-embedding-004'

_index = None


def _embed(texts, task_type='retrieval_document'):
    import google.generativeai as genai
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=texts,
        task_type=task_type,
    )
    return result['embedding']


def _chunk_document(text):
    parts = re.split(r'\n\s*\n', text.strip())
    chunks = [p.strip() for p in parts if p.strip()]
    return [c for c in chunks if not c.startswith('Species:')]


def _cosine_sim(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _build_index():
    global _index
    if _index is not None:
        return _index

    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            _index = json.load(f)
        return _index

    if not os.path.isdir(DOCS_DIR):
        _index = {'chunks': [], 'embeddings': [], 'metadatas': []}
        return _index

    chunks, metadatas = [], []
    for fname in sorted(os.listdir(DOCS_DIR)):
        if not fname.endswith('.txt'):
            continue
        species_key = fname[:-4]
        with open(os.path.join(DOCS_DIR, fname), 'r', encoding='utf-8') as f:
            content = f.read()
        for chunk in _chunk_document(content):
            chunks.append(chunk)
            metadatas.append({'source': fname, 'species_key': species_key})

    if not chunks:
        _index = {'chunks': [], 'embeddings': [], 'metadatas': []}
        return _index

    embeddings = _embed(chunks, task_type='retrieval_document')
    _index = {'chunks': chunks, 'embeddings': embeddings, 'metadatas': metadatas}

    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(_index, f)

    return _index


def warmup():
    try:
        _build_index()
    except Exception:
        pass


def pretty_source(filename):
    name = filename[:-4] if filename.endswith('.txt') else filename
    return name.replace('_', ' ').title() + ' Care Reference'


def retrieve(species, query, k=3):
    try:
        index = _build_index()
        if not index['chunks']:
            return []
        search_text = f'{species}: {query}'.strip(': ')
        query_emb = _embed([search_text], task_type='retrieval_query')[0]

        scored = []
        for i, emb in enumerate(index['embeddings']):
            scored.append((_cosine_sim(query_emb, emb), i))
        scored.sort(reverse=True)

        return [{'text': index['chunks'][i], 'source': index['metadatas'][i].get('source', 'reference')}
                for _, i in scored[:k]]
    except Exception:
        return []
