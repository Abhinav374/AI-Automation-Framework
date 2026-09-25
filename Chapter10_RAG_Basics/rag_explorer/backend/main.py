from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from groq import Groq
except ImportError:  # pragma: no cover - dependency is installed by requirements.txt
    Groq = None


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
PDF_PATH = next(ROOT.glob("Product Requirements Document*.pdf"), None)
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
CHUNK_SIZE = 850
CHUNK_OVERLAP = 140


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def split_into_chunks(text: str) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def load_document() -> list[dict[str, Any]]:
    if PDF_PATH is None:
        raise RuntimeError("No VWO PDF was found in the Chapter10_RAG_Basics folder.")
    reader = PdfReader(str(PDF_PATH))
    chunks: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = clean_text(page.extract_text())
        for chunk_index, text in enumerate(split_into_chunks(page_text), start=1):
            chunks.append(
                {
                    "id": f"p{page_number}-c{chunk_index}",
                    "page": page_number,
                    "text": text,
                }
            )
    return chunks


CHUNKS = load_document()
VECTORIZER = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
MATRIX = VECTORIZER.fit_transform([chunk["text"] for chunk in CHUNKS])

app = FastAPI(title="VWO RAG Explorer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def retrieve(question: str, limit: int = 3) -> list[dict[str, Any]]:
    scores = cosine_similarity(VECTORIZER.transform([question]), MATRIX)[0]
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:limit]
    return [
        {**CHUNKS[index], "score": round(float(score), 4), "rank": rank}
        for rank, (index, score) in enumerate(ranked, start=1)
    ]


def answer_with_groq(question: str, results: list[dict[str, Any]]) -> tuple[str, str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or Groq is None:
        return (
            "Groq is not configured. The ranked chunks below are still the local RAG result.",
            "local-only",
        )
    context = "\n\n".join(
        f"[Chunk {item['rank']} | page {item['page']} | score {item['score']}]\n{item['text']}"
        for item in results
    )
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        max_tokens=500,
        messages=[
            {
                "role": "system",
                "content": "Answer only from the supplied document context. If the answer is not present, say so. Cite page numbers inline.",
            },
            {"role": "user", "content": f"Question: {question}\n\nDocument context:\n{context}"},
        ],
    )
    return response.choices[0].message.content or "No answer returned.", MODEL


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ready", "chunks": len(CHUNKS), "pages": len({item["page"] for item in CHUNKS})}


@app.get("/api/document")
def document() -> dict[str, Any]:
    return {
        "filename": PDF_PATH.name if PDF_PATH else "missing",
        "pages": len({item["page"] for item in CHUNKS}),
        "chunks": len(CHUNKS),
        "chunk_size": CHUNK_SIZE,
        "overlap": CHUNK_OVERLAP,
        "embedding": "TF-IDF (local, open-source baseline)",
        "vector_store": "in-memory cosine similarity",
        "items": CHUNKS,
    }


@app.post("/api/query")
def query(request: QueryRequest) -> dict[str, Any]:
    try:
        results = retrieve(request.question)
        answer, model = answer_with_groq(request.question, results)
        return {"question": request.question, "answer": answer, "model": model, "results": results}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error