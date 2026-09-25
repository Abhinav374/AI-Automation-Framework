# VWO RAG Explorer

This small teaching app ingests the bundled VWO PRD PDF, extracts page text, creates overlapping chunks, ranks the top three chunks with local TF-IDF cosine similarity, and sends those chunks to Groq for a grounded answer.

## Run on Windows

From `Chapter10_RAG_Basics`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\rag_explorer\requirements.txt
uvicorn rag_explorer.backend.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd .\rag_explorer\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The backend reads `GROQ_API_KEY` from the existing `.env` one directory above `rag_explorer`. Set `GROQ_MODEL` there if your Groq account uses a different model; the default is `openai/gpt-oss-120b`.