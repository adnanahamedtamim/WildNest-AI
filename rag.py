"""Lightweight local RAG for WildNest AI.

Retrieves relevant species care-reference chunks (from rag/documents/) to ground
and cite answers with real sources. This is STRICTLY SECONDARY: the pet's own
profile, medical history, and logged analytics (temperature, humidity, weight,
feeding, stress, activity) always come first and are never overridden by anything
retrieved here — see build_system_context() in wildsight_ai.py for how the two
are combined. Runs entirely locally (embeddings + vector search) — no API calls,
no effect on Gemini quota. Any failure here degrades silently to "no reference
material available" rather than breaking the core chat, which always works.
"""
import os
import re

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(_BASE_DIR, 'rag', 'documents')
DB_DIR = os.path.join(_BASE_DIR, 'rag', 'vectordb')
COLLECTION_NAME = 'wildnest_care_docs'
EMBED_MODEL_NAME = 'all-MiniLM-L6-v2'

_collection = None
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBED_MODEL_NAME)
    return _embedder


def _chunk_document(text):
    """Split into paragraph-level chunks (blank-line separated), stripped.
    Drops the leading 'Species: ... Care Reference' title line — it's pure
    metadata with no retrievable content, and its short/generic embedding was
    observed crowding out genuinely relevant chunks in top-k search."""
    parts = re.split(r'\n\s*\n', text.strip())
    chunks = [p.strip() for p in parts if p.strip()]
    return [c for c in chunks if not c.startswith('Species:')]


def _index_documents(collection):
    if not os.path.isdir(DOCS_DIR):
        return
    embedder = _get_embedder()
    ids, texts, metadatas = [], [], []
    for fname in sorted(os.listdir(DOCS_DIR)):
        if not fname.endswith('.txt'):
            continue
        species_key = fname[:-4]
        with open(os.path.join(DOCS_DIR, fname), 'r', encoding='utf-8') as f:
            content = f.read()
        for i, chunk in enumerate(_chunk_document(content)):
            ids.append(f'{species_key}-{i}')
            texts.append(chunk)
            metadatas.append({'source': fname, 'species_key': species_key})
    if not texts:
        return
    embeddings = embedder.encode(texts).tolist()
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    os.makedirs(DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=DB_DIR)
    _collection = client.get_or_create_collection(COLLECTION_NAME)
    if _collection.count() == 0:
        _index_documents(_collection)
    return _collection


def warmup():
    """Eagerly load BOTH the embedding model AND the vector index. Takes ~20-40s
    the very first time, then is instant afterwards. Call this once at APP
    STARTUP (in a background thread) so that cost never lands on whichever user
    happens to send the first chat message.

    IMPORTANT: _get_embedder() must be called explicitly here — _get_collection()
    alone does NOT load it once the vector store already has documents indexed
    (the embedder is only touched during indexing, or later during an actual
    retrieve() call to encode the query). Skipping this was a real bug: the
    collection warmed up in ~2s while the embedder — where the real 20-40s
    cost lives — stayed cold until the first real user request hit it anyway."""
    try:
        _get_embedder()
        _get_collection()
    except Exception:
        pass  # warmup is a nice-to-have; retrieve() will just lazy-load on first real use


def pretty_source(filename):
    """'sulcata_tortoise.txt' -> 'Sulcata Tortoise Care Reference'"""
    name = filename[:-4] if filename.endswith('.txt') else filename
    return name.replace('_', ' ').title() + ' Care Reference'


def retrieve(species, query, k=3):
    """Return up to k relevant reference chunks as [{'text', 'source'}, ...].
    Returns [] on ANY failure (missing docs, model load issue, etc.) — RAG is a
    bonus layer that must never break the core chat, which works fine without it."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []
        embedder = _get_embedder()
        search_text = f'{species}: {query}'.strip(': ')
        query_embedding = embedder.encode([search_text]).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=k)
        docs = (results.get('documents') or [[]])[0]
        metas = (results.get('metadatas') or [[]])[0]
        return [{'text': d, 'source': m.get('source', 'reference')} for d, m in zip(docs, metas)]
    except Exception:
        return []
