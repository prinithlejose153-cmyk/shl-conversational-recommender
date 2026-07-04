# SHL Conversational Assessment Recommender

A conversational AI agent that helps hiring managers find the right SHL Individual Test Solutions through natural dialogue — built for the SHL AI Research Intern take-home assignment.


**Live API:** https://shl-assessment-recommender-ra3n.onrender.com

**Swagger UI:** https://shl-assessment-recommender-ra3n.onrender.com/docs

## Features

- Conversational recommendation workflow for SHL assessments
- BM25 retrieval over the SHL catalog
- Prompt injection and off-topic guardrails
- Deterministic recommendation fallback
- Catalog-backed URL validation
- Stateless REST API
- Interactive Swagger documentation
- Production deployment on Render
- JSON-schema compliant responses for evaluator compatibility
  

---

## Architecture

```
POST /chat
   │
   ├─ Regex Guardrails (pre-LLM, deterministic)
   │    └─ Blocks: prompt injection / legal advice / off-topic
   │
   ├─ BM25 Retrieval (rank-bm25)
   │    └─ Top-20 catalog candidates injected into prompt
   │
   ├─ Groq LLM  (llama-3.3-70b-versatile, JSON mode)
   │    └─ Produces: reply + recommendations + end_of_conversation
   │
   ├─ Post-LLM Validation
   │    └─ Every URL checked against catalog index; repaired by name if needed
   │
   └─ Deterministic Force-Recommend Fallback
        └─ If LLM returns 0 recs despite clear role/skill context → top-5 BM25 candidates returned
```

**Stack:** FastAPI · Groq (llama-3.3-70b-versatile) · rank-bm25 · httpx · Pydantic v2 · Render

---

## Quickstart (local)

### 1. Create a Groq API key
Go to **https://console.groq.com** → API Keys → Create API Key. 

Groq was selected because it provides low-latency inference and an OpenAI-compatible API, making it well suited for deterministic JSON-based conversational workflows.

> Recommended Python version: **3.11**

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variable and run
```bash
export GROQ_API_KEY="gsk_..."          # Mac/Linux
$env:GROQ_API_KEY="gsk_..."            # Windows PowerShell

uvicorn app.main:app --reload --port 8000
```

### 4. Test
```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I am hiring a mid-level Java developer with Spring experience"},
      {"role": "assistant", "content": "What seniority level are you targeting?"},
      {"role": "user", "content": "Mid-level, around 4 years"}
    ]
  }'
```

---

## API Reference

### `GET /health`
```json
{"status": "ok"}
```

### `GET /`
```json
{
  "service": "SHL Conversational Assessment Recommender",
  "status": "running",
  "version": "1.0.0",
  "documentation": "/docs",
  "health": "/health",
  "chat_endpoint": "/chat"
}
```

### `POST /chat`

**Request:**
```json
{
  "messages": [
    {"role": "user",      "content": "I need to hire a Python data scientist"},
    {"role": "assistant", "content": "What seniority level are you targeting?"},
    {"role": "user",      "content": "Senior, 6+ years"}
  ]
}
```

**Response:**
```json
{
  "reply": "Here are 5 assessments well-suited for a senior Python data scientist.",
  "recommendations": [
    {"name": "Python (New)",       "url": "https://www.shl.com/products/product-catalog/view/python-new/",        "test_type": "K"},
    {"name": "Data Science (New)", "url": "https://www.shl.com/products/product-catalog/view/data-science-new/", "test_type": "K"},
    {"name": "Machine Learning (New)", "url": "https://www.shl.com/products/product-catalog/view/machine-learning-new/", "test_type": "K"}
  ],
  "end_of_conversation": false
}
```

**Schema rules (non-negotiable per assignment spec):**
- `reply` — always a non-empty string
- `recommendations` — empty `[]` when clarifying/refusing; 1–10 items when recommending
- `end_of_conversation` — `true` only when task is complete
- Every `url` comes from the scraped SHL catalog — never invented

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | — | Groq API key from console.groq.com |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |

---

## Deploy to Render

1. Push this repo to GitHub (commit `data/catalog.json`)
2. Go to **dashboard.render.com** → New Web Service → connect repo
3. Render auto-reads `render.yaml`
4. Add `GROQ_API_KEY` in the **Environment** tab
5. Deploy — your URL will be `https://<name>.onrender.com`
6. Trigger **Deploy Latest Commit** from the Render dashboard after pushing changes.

> Render free tier sleeps after 15 min inactivity. The assignment allows up to 2 min for the first `/health` wake-up call.

---

## Project Structure

```
app/
  main.py        FastAPI app — endpoints: GET /, GET /health, POST /chat
  schemas.py     Pydantic request/response models (exact assignment spec)
  retrieval.py   BM25 catalog index — search(), find_by_name(), is_valid_url()
  agent.py       Orchestration: guardrails → retrieval → LLM → validate → fallback
  llm.py         Async Groq HTTP client (OpenAI-compatible, JSON mode)
  prompts.py     System prompt + conversation formatter

data/
  catalog.json   155 SHL Individual Test Solutions with descriptions, job levels, URLs

scripts/
  scrape_catalog.py    Two-pass scraper (run if you want to refresh catalog)
  validate_catalog.py  Validates catalog.json after scraping
  final_check.py       Pre-submission checks against a live URL

eval/
  test_probes.py  20 behavior probes covering all scoring dimensions

render.yaml      Render free-tier deploy config
requirements.txt
```

---


## Design Assumptions

- Conversation history is supplied with every `/chat` request.
- Recommendations are restricted to the scraped SHL catalog.
- BM25 is used for lexical retrieval rather than semantic embeddings.
- The LLM generates responses only from the retrieved candidate set.


## Evaluation Results

| Check | Result |
|---|---|
| Schema compliance (every response) | ✅ Pass |
| Vague query → 0 recommendations | ✅ Pass |
| Context turn → ≥1 recommendation | ✅ Pass |
| Injection → 0 recommendations | ✅ Pass |
| Legal query → 0 recommendations | ✅ Pass |
| All URLs from SHL catalog | ✅ Pass |
| Response under 30s | ✅ Pass |
| Official evaluator score | **22/22** |

The service was validated locally and against the deployed Render instance using the provided evaluation scripts and behavioral probes.



---

## Notes

- The API is fully stateless; clients must send the complete conversation history with each `/chat` request.
- Recommendations are restricted to assessments present in the SHL catalog.
- Groq (`llama-3.3-70b-versatile`) is used for low-latency JSON generation.
- URL validation and deterministic fallback improve reliability while preserving catalog correctness.