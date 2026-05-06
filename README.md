# עוזר משפטי — Hebrew Legal RAG System

מערכת RAG ציבורית בעברית למידע משפטי.  
**Stack:** Python 3.11 / FastAPI · React 18 + Vite · Qdrant Cloud · Voyage · Cohere · Claude (Anthropic)

---

## ארכיטקטורה בקצרה

```
User (Hebrew Chat)
  └─ React + Vite (RTL, SSE streaming)
       └─ POST /api/chat  (FastAPI)
            ├─ Query expansion: 2 paraphrases + HyDE  (Claude Haiku)
            ├─ Voyage embed × 4 variants
            ├─ Hybrid retrieval (Qdrant dense + BM25) + RRF → top-30 children
            ├─ Cohere rerank-multilingual-v3 → top-6
            ├─ Parent-Document expansion (child → full section)
            ├─ Confidence < threshold? → Tavily site:kolzchut.org.il + trafilatura
            ├─ Router: Opus 4 (complex) / Sonnet 4.6 (routine)
            ├─ Stream answer + Hebrew prompt (citation-mandatory)
            └─ Citation verification (exact substring) → source cards
```

---

## מבנה הריפו

```
rag-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI: /api/chat (SSE), /api/samples, /healthz
│   │   ├── config.py            # Pydantic Settings
│   │   ├── pipeline.py          # orchestrator
│   │   ├── rate_limit.py        # slowapi + Turnstile + token budget
│   │   ├── ingest/
│   │   │   ├── pdf_loader.py    # Azure DI Layout + PyMuPDF fallback
│   │   │   ├── chunker.py       # parent (section) → child (~300 tokens)
│   │   │   ├── contextualize.py # Claude Haiku + prompt caching
│   │   │   └── build_index.py   # CLI: PDFs → Qdrant + BM25
│   │   ├── retrieval/
│   │   │   ├── embedder.py      # Voyage voyage-3-large
│   │   │   ├── vectorstore.py   # Qdrant hybrid + RRF
│   │   │   ├── query_expansion.py
│   │   │   ├── parent_doc.py
│   │   │   └── reranker.py      # Cohere rerank-multilingual-v3
│   │   ├── web/
│   │   │   └── kolzchut_search.py  # Tavily + trafilatura + mini-rerank
│   │   ├── generation/
│   │   │   ├── llm.py           # Anthropic streaming
│   │   │   ├── router.py        # Opus / Sonnet router
│   │   │   ├── prompts.py       # Hebrew system prompt
│   │   │   └── citations.py     # exact substring verify
│   │   ├── samples/
│   │   │   └── generate_faq.py  # CLI: generate + vet sample questions
│   │   └── eval/
│   │       ├── gold_set.json    # 30-50 Q+A+sources
│   │       ├── runner.py        # RAGAS eval (CI gate)
│   │       └── ragas_metrics.py # thresholds
│   ├── data/{pdfs/, eval/}
│   ├── requirements.txt
│   ├── Dockerfile
│   └── render.yaml
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/{MessageBubble, SourceCard, SampleQuestions, ChatInput}.tsx
│   │   ├── hooks/useChat.ts
│   │   └── lib/{api.ts, types.ts}
│   ├── package.json
│   └── vercel.json
├── docker-compose.yml
└── .env.example
```

---

## התקנה מהירה (local dev)

### 1. העתק secrets
```bash
cp .env.example .env
# מלא את כל המשתנים ב-.env
```

### 2. הפעל עם Docker Compose
```bash
docker-compose up --build
```
Frontend: http://localhost:5173 · Backend: http://localhost:8000

### 3. אינדוקס קבצי PDF (פעם אחת)
```bash
# הכנס PDF-ים לתוך backend/data/pdfs/
docker-compose exec backend python -m app.ingest.build_index
```

### 4. צור שאלות לדוגמה
```bash
docker-compose exec backend python -m app.samples.generate_faq --max-questions 15
```

---

## הרצה ידנית (ללא Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env  # ומלא
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

---

## Eval Harness (RAGAS)

מלא את `backend/data/eval/gold_set.json` עם 30–50 שאלות ותשובות.

```bash
docker-compose exec backend python -m app.eval.runner
```

סף מינימום:
| מדד | סף |
|---|---|
| faithfulness | ≥ 0.85 |
| answer_relevancy | ≥ 0.80 |
| context_recall | ≥ 0.80 |
| context_precision | ≥ 0.75 |

יציאה עם קוד 1 אם מדד כלשהו נכשל (חוסם deploy ב-CI).

---

## Deploy

### Backend → Render
1. חבר ריפו GitHub ל-Render
2. הגדר `Root Directory: backend`, `Dockerfile`
3. הכנס את כל משתני הסביבה מ-`.env.example`

### Frontend → Vercel
1. `cd frontend && vercel --prod`
2. הגדר `VITE_API_URL` ל-URL של Render
3. עדכן `vercel.json` עם ה-URL של Render

---

## משתני סביבה

| משתנה | תיאור |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `VOYAGE_API_KEY` | Voyage AI key |
| `COHERE_API_KEY` | Cohere key |
| `TAVILY_API_KEY` | Tavily search key |
| `AZURE_DI_ENDPOINT` | Azure Document Intelligence endpoint |
| `AZURE_DI_KEY` | Azure DI key |
| `QDRANT_URL` | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `TURNSTILE_SECRET` | Cloudflare Turnstile secret (ריק = דולג) |
| `DAILY_TOKEN_BUDGET` | מגבלת טוקנים יומית (ברירת מחדל: 500,000) |
| `CONFIDENCE_THRESHOLD` | סף rerank להפעלת fallback (ברירת מחדל: 0.35) |

---

## הערות

- **אין תרגום** — Voyage + Cohere תומכים בעברית מצוין. תרגום משפטי גורם לאיבוד משמעות.
- **Contextual Retrieval** — Claude Haiku עם prompt caching מייצר prefix לכל child chunk לפני embedding.
- **ציטוטים מאומתים בלבד** — ציטוט שאינו substring מדויק של parent מוסר אוטומטית.
- **Router** — שאלות מורכבות → Opus 4, שגרתיות → Sonnet 4.6.
