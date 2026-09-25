import { useEffect, useState } from "react";
import { ArrowUpRight, BookOpen, BrainCircuit, FileText, Search, Sparkles } from "lucide-react";

const API = "http://localhost:8000/api";
type Chunk = { id: string; page: number; text: string; score?: number; rank?: number };
type DocumentInfo = { filename: string; pages: number; chunks: number; chunk_size: number; overlap: number; embedding: string; vector_store: string; items: Chunk[] };
type QueryResult = { answer: string; model: string; results: Chunk[] };

const starterQuestions = ["What are the main authentication requirements?", "How is accessibility handled?", "What are the key login success metrics?"];

export function App() {
  const [document, setDocument] = useState<DocumentInfo | null>(null);
  const [question, setQuestion] = useState(starterQuestions[0]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { fetch(`${API}/document`).then((response) => response.json()).then(setDocument).catch(() => setError("Start the FastAPI server to connect the explorer.")); }, []);

  async function ask(nextQuestion = question) {
    if (!nextQuestion.trim()) return;
    setLoading(true); setError("");
    try {
      const response = await fetch(`${API}/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: nextQuestion }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Query failed");
      setResult(payload);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Query failed"); }
    finally { setLoading(false); }
  }

  return <main className="shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">V</span><span>RAG / EXPLORER</span></div><div className="status"><span className="pulse" />LOCAL PIPELINE <span className="slash">/</span> GROQ READY</div></header>
    <section className="hero"><div className="eyebrow"><Sparkles size={15} /> DOCUMENT INTELLIGENCE LAB</div><h1>Ask the brief.<br /><em>See the retrieval.</em></h1><p className="intro">A transparent RAG walkthrough for the VWO Login Dashboard requirements. Every answer starts with the chunks you can inspect.</p></section>
    <section className="stats">{[[FileText, document?.filename || "Loading PDF", "SOURCE DOCUMENT"], [BookOpen, document ? `${document.pages} pages` : "...", "EXTRACTED"], [BrainCircuit, document ? `${document.chunks} chunks` : "...", "INDEXED LOCALLY"]].map(([Icon, value, label]) => <div className="stat" key={String(label)}><Icon size={18} /><div><strong>{String(value)}</strong><span>{String(label)}</span></div></div>)}</section>
    <section className="workspace">
      <div className="query-panel"><div className="section-label">01 / QUERY THE DOCUMENT</div><h2>What do you want to find?</h2><div className="search-box"><Search size={19} /><input value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") ask(); }} /><button onClick={() => ask()} disabled={loading}>{loading ? "Thinking" : "Ask"}<ArrowUpRight size={17} /></button></div><div className="suggestions">{starterQuestions.map((item) => <button key={item} onClick={() => { setQuestion(item); ask(item); }}>{item}</button>)}</div>{error && <p className="error">{error}</p>}<div className="answer"><div className="answer-head"><span>GROQ RESPONSE</span><span className="model">{result?.model || "awaiting query"}</span></div><p>{result?.answer || "Your answer will appear here, grounded in the three highest-scoring chunks."}</p></div></div>
      <aside className="method"><div className="section-label">PIPELINE NOTES</div><h3>How this RAG works</h3><ol><li><b>Extract</b><span>Read text from each PDF page with pypdf.</span></li><li><b>Chunk</b><span>Split into {document?.chunk_size || 850}-word windows with {document?.overlap || 140}-word overlap.</span></li><li><b>Retrieve</b><span>Compare the question against every chunk with local TF-IDF cosine similarity.</span></li><li><b>Generate</b><span>Send only the top three chunks to the Groq model.</span></li></ol></aside>
    </section>
    <section className="results"><div className="results-title"><div><div className="section-label">02 / RETRIEVAL TRACE</div><h2>Top chunks <span>({result?.results.length || 0}/3)</span></h2></div>{result && <div className="trace-pill">QUERY RANKED LOCALLY <span>●</span></div>}</div>{result?.results.length ? <div className="chunk-grid">{result.results.map((chunk) => <article className="chunk" key={chunk.id}><div className="chunk-meta"><span className="rank">0{chunk.rank}</span><span>PAGE {chunk.page}</span><span className="score">{((chunk.score || 0) * 100).toFixed(1)}% MATCH</span></div><p>{chunk.text}</p><div className="bar"><i style={{ width: `${Math.max((chunk.score || 0) * 100, 4)}%` }} /></div></article>)}</div> : <div className="empty"><Search size={22} /><p>Run a question to see the exact evidence selected for the answer.</p></div>}</section>
    <footer><span>VWO LOGIN DASHBOARD / RAG EXPLORER</span><span>{document ? `${document.embedding} · ${document.vector_store}` : "PDF INGESTION SYSTEM"}</span></footer>
  </main>;
}