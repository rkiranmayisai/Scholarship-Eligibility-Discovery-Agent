"""
TOOL: Vector Search Tool (RAG retrieval layer)
Used by: Scholarship Discovery Agent

Implements a lightweight, fully-local Retrieval-Augmented-Generation
retrieval step over the scholarship knowledge base. We use scikit-learn's
TF-IDF vectorizer + cosine similarity rather than a hosted embeddings API,
so retrieval works with zero network access / zero API keys -- while
remaining a genuine vector-similarity search over a document corpus,
matching the RAG requirement (see FAISS/Chroma/pgvector note in README
for swapping in a production vector DB).

Every retrieved scholarship carries its source record so recommendations
are always traceable back to the underlying data (no hallucinated
scholarships).
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.tools.scholarship_db_tool import load_all_scholarships


def _doc_text(s: dict) -> str:
    return " ".join(str(x) for x in [
        s.get("name", ""),
        s.get("provider", ""),
        s.get("description", ""),
        " ".join(s.get("eligible_courses", []) or []),
        " ".join(s.get("eligible_states", []) or []),
        " ".join(s.get("category_conditions", []) or []),
    ])


def build_index(scholarships: list):
    docs = [_doc_text(s) for s in scholarships]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(docs)
    return vectorizer, matrix


def semantic_search(query: str, scholarships: list, top_k: int = 20) -> list:
    """
    Returns scholarships ranked by TF-IDF cosine similarity to `query`,
    each annotated with a `_retrieval_score` for transparency.
    """
    if not scholarships:
        scholarships = load_all_scholarships()
    vectorizer, matrix = build_index(scholarships)
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix).flatten()
    ranked_idx = scores.argsort()[::-1][:top_k]
    results = []
    for i in ranked_idx:
        item = dict(scholarships[i])
        item["_retrieval_score"] = round(float(scores[i]), 4)
        results.append(item)
    return results


def build_query_from_profile(profile: dict) -> str:
    parts = [
        profile.get("course") or "",
        profile.get("branch") or "",
        profile.get("state") or "",
        profile.get("category") or "",
        profile.get("gender") or "",
        "scholarship for students in " + (profile.get("state") or "India"),
    ]
    return " ".join(p for p in parts if p)
