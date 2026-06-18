# Enterprise Advanced RAG — Kubernetes SRE Copilot :CorexRAG

> LangGraph · Hybrid Search · CRAG · Self-RAG · Text2SQL (HITL) · 5-Tier Cache · 9-Layer Guardrails

A production-grade RAG system for Kubernetes IT operations built with FastAPI, LangGraph, Qdrant, PostgreSQL, Redis, and Streamlit.

## Architecture

```
SRE/User → FastAPI → 9-Layer Input Security → LangGraph State Machine
                                                   ├── RAG Pipeline (HyDE → Hybrid Retrieval → RRF → Rerank → CRAG → Self-RAG)
                                                   └── Text2SQL Pipeline (GPT-4o → Validate → HITL → Execute)
                                               → 5-Tier Redis Cache → Response
```
# 🔄 Workflow Diagram

```mermaid
flowchart TD

%% Nodes Styling
classDef user fill:#0ea5e9,color:#fff,stroke:#0369a1,stroke-width:2px;
classDef api fill:#6366f1,color:#fff,stroke:#4338ca,stroke-width:2px;
classDef input fill:#f97316,color:#fff,stroke:#c2410c,stroke-width:2px;
classDef rag fill:#3b82f6,color:#fff,stroke:#1d4ed8,stroke-width:2px;
classDef sql fill:#10b981,color:#fff,stroke:#047857,stroke-width:2px;
classDef llm fill:#ec4899,color:#fff,stroke:#be185d,stroke-width:2px;
classDef cache fill:#ef4444,color:#fff,stroke:#b91c1c,stroke-width:2px;
classDef output fill:#dc2626,color:#fff,stroke:#991b1b,stroke-width:2px;
classDef db fill:#14b8a6,color:#fff,stroke:#0f766e,stroke-width:2px;
classDef decision fill:#8b5cf6,color:#fff,stroke:#6d28d9,stroke-width:2px;

%% Main Nodes
U[SRE / User]
F[FastAPI Service]

%% Input Security
subgraph INPUT["🛡️ Input Security Pipeline"]
    I1[Pydantic + Regex]
    I2[JWT Auth]
    I3[Rate Limit]
    I4[Token Budget]
    I5[Input Restructure]
    I6[LLM Guard Scan]
    I7[Content Moderation]
end

%% Cache Layer
subgraph CACHE["⚡ 5-Tier Redis Cache"]
    C1[Embedding]
    C2[Intent Router]
    C3[SQL Gen]
    C4[SQL Result]
    C5[RAG Answer]
end

%% LangGraph
subgraph LANGGRAPH["🧠 LangGraph State Machine"]

    R{Intent Router}

    subgraph RAG["📘 RAG Pipeline"]
        H[HyDE]
        E[Embed Query]
        HR[Hybrid Retrieval]
        RF[RRF Fusion]
        RR[Cross-Encoder Rerank]
        CG[CRAG Grader]
        SP[Spotlighting]
        TV[Tavily Fallback]
    end

    subgraph SQL["🗄️ Text2SQL Pipeline"]
        GS[Generate SQL]
        VS[Validate SQL]
        HITL[Human Approval]
        EX[Execute SQL]
        FR[Format Results]
    end

    LG[LLM Answer Generation]
    SR[Self-RAG Reflect]
    FN[Finalize + Metadata]
end

%% Output Security
subgraph OUTPUT["🚨 Output Security"]
    O1[Output Moderation]
    O2[PII Redaction]
    O3[Schema Validation]
end

%% Data Stores
subgraph STORES["💾 Persistent Data Stores"]
    Q[Qdrant]
    P[PostgreSQL]
    S[S3 / Local FS]
    OA[OpenAI API]
    T[Tavily API]
end

%% Main Flow
U --> F
F --> I1
I1 --> I2 --> I3 --> I4 --> I5 --> I6 --> I7
I7 --> R

%% Cache Connection
F --> C1
F --> C2
F --> C3
F --> C4
F --> C5

%% Intent Routing
R -->|rag / hybrid| H
R -->|sql / hybrid| GS

%% RAG Flow
H --> E --> HR --> RF --> RR --> CG --> SP
CG -->|low relevance| TV
TV --> SP
SP --> LG

%% SQL Flow
GS --> VS --> HITL --> EX --> FR --> LG

%% Self Reflection
LG --> SR
SR -->|score < 0.8| LG
LG --> FN

%% Output Security
FN --> O1 --> O2 --> O3 --> U

%% Store Connections
HR --> Q
EX --> P
SP --> S
H --> OA
GS --> OA
TV --> T

%% Apply Styles
class U user;
class F api;

class I1,I2,I3,I4,I5,I6,I7 input;
class H,E,HR,RF,RR,CG,SP,TV rag;
class GS,VS,HITL,EX,FR sql;
class LG,SR,FN llm;
class C1,C2,C3,C4,C5 cache;
class O1,O2,O3 output;
class Q,P,S,OA,T db;
class R decision;
```
## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill environment variables
cp .env.example .env

# 3. Start infrastructure
docker-compose up -d

# 4. Seed data (K8s docs)
python scripts/seed_data.py

# 5. Run API
uvicorn app.main:app --reload

# 6. Open Streamlit UI
streamlit run app/ui/streamlit_app.py
```

## Project Structure

```
enterprise-rag/
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── api/
│   │   ├── routes.py            # REST endpoints
│   │   └── models.py            # Pydantic request/response models
│   ├── core/
│   │   ├── graph.py             # LangGraph state machine
│   │   ├── intent_router.py     # rag / sql / hybrid routing
│   │   └── state.py             # Graph state schema
│   ├── pipelines/
│   │   ├── rag/
│   │   │   ├── hyde.py          # Hypothetical Document Embeddings
│   │   │   ├── retrieval.py     # Hybrid retrieval (Dense + BM25)
│   │   │   ├── rerank.py        # Cross-encoder reranking
│   │   │   ├── crag.py          # CRAG grader + web fallback
│   │   │   ├── self_rag.py      # Self-RAG reflection loop
│   │   │   └── spotlighting.py  # XML-delimited context
│   │   └── sql/
│   │       ├── generator.py     # Text2SQL with GPT-4o
│   │       ├── validator.py     # SELECT-only + blocklist
│   │       └── executor.py      # Postgres execution
│   ├── cache/
│   │   └── redis_cache.py       # 5-tier TTL cache (Upstash)
│   ├── guardrails/
│   │   ├── input_pipeline.py    # 9-layer input security
│   │   └── output_pipeline.py   # Output moderation + PII redaction
│   └── utils/
│       ├── embeddings.py        # text-embedding-3-small wrapper
│       └── llm.py               # GPT-4o wrapper
├── scripts/
│   ├── seed_data.py             # Ingest K8s docs into Qdrant
│   └── run_evals.py             # Ragas evaluation suite
├── tests/
│   └── test_pipeline.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

# ⚡ Features

# 1. Hybrid Retrieval

Combines:

- Dense vector retrieval (Qdrant)
- Sparse retrieval (BM25)
- Reciprocal Rank Fusion

Improves:

- Recall
- Precision
- Context quality

---

# 2. HyDE (Hypothetical Document Embeddings)

Query augmentation using synthetic answers.

Pipeline:

```text
Question → Generate 3 hypothetical answers → Embed → Retrieve
```

Improves semantic search significantly.

---

# 3. Cross Encoder Re-ranking

Ranks retrieved chunks using:

- BGE Reranker
- Voyage AI reranker

Improves final context relevance.

---

# 4. CRAG (Corrective RAG)

Confidence-based retrieval correction.

If confidence < threshold:

```text
Fallback → Tavily Search
```

Prevents weak retrieval.

---

# 5. Self-RAG Reflection

Model evaluates its own response:

- Hallucination score
- Relevance score
- Grounding score

Regenerates if below threshold.

---

# 6. Text2SQL Pipeline

Converts natural language into SQL.

Supports:

- PostgreSQL
- Read-only SELECT
- Schema-aware generation
- Human approval before execution

---

# 7. Multi-layer Guardrails

## Input

| Layer | Purpose |
|---|---|
| Regex Guard | Detect prompt injections |
| JWT Auth | Authentication |
| Rate Limiter | Prevent abuse |
| Token Budget | Cost control |
| Restructuring | Normalize payload |
| LLM Guard | Toxicity scan |
| Content Filter | Safety |
| PII Scan | Sensitive data |

---

## Output

- PII Redaction
- Content Moderation
- Schema Validation
- Retry-on-invalid-response

---

# 8. 5-Tier Redis Cache

| Tier | Data | 
|---|---|
| Tier 1 | Embeddings |
| Tier 2 | Intent |
| Tier 3 | SQL Gen |
| Tier 4 | SQL Results | 
| Tier 5 | Final RAG Answer | 

---

# 🛠 Tech Stack

## Backend

- FastAPI
- LangGraph
- Pydantic
- SQLAlchemy

## AI / LLM

- GPT-4o
- text-embedding-3-small

## Retrieval

- Qdrant
- BM25
- BGE Reranker

## Databases

- PostgreSQL
- Redis

## External APIs

- Tavily Search API
- OpenAI API

## Frontend

- Streamlit

## DevOps

- Docker
- Docker Compose


---

# ⚙️ Installation

## Clone Repository

```bash
git clone https://github.com/AnjaliYadav-04/CortexRAG_Intelligence.git
cd Enterprise_RAG
```

---

## Create Virtual Environment

```bash
python -m venv myenv
```

Activate:

```bash
myenv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Create `.env`

```env
OPENAI_API_KEY=sk-...
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=k8s_docs
POSTGRES_DSN=postgresql://rag:rag@localhost:5432/ragdb
REDIS_URL=redis://localhost:6379
 For Upstash: REDIS_URL=rediss://default:<token>@<host>.upstash.io:6380
TAVILY_API_KEY=tvly-...
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
LOG_LEVEL=INFO
RATE_LIMIT_PER_MIN=20
TOKEN_BUDGET_PER_DAY=100000
CRAG_RELEVANCE_THRESHOLD=0.7
SELF_RAG_SCORE_THRESHOLD=0.8
SELF_RAG_MAX_RETRIES=2
```

---

# 🐳 Run with Docker

```bash
docker-compose up --build
```

---

# ▶ Run Locally

API:

```bash
uvicorn app.main:app --reload
```

UI:

```bash
streamlit run app/ui/app.py
```

---

# 📊 Evaluation Metrics

Uses **RAGAS** for evaluation.

Measures:

- Faithfulness
- Context Recall
- Answer Relevancy
- Precision@K
- SQL Accuracy

Run:

```bash
python scripts/run_eval.py
```

---

# 🚀 Future Roadmap

- Kubernetes auto-remediation
- Grafana integration
- Slack bot
- Incident timeline summarization
- Agent memory
- Multi-agent orchestration
- Cost observability
- Prompt analytics

---

# 💡 Example Queries

### Kubernetes RCA

```text
Why is my pod in CrashLoopBackOff?
```

---

### Incident Search

```text
Show incidents related to memory leaks in namespace prod
```

---

### SQL Query

```text
How many incidents happened in the last 30 days?
```

---

### Security Check

```text
Which deployments have failed liveness probes?
```

---

# 👩‍💻 Author

### Anjali Yadav

AI Engineer | RAG Systems | MLOps | LLMOps | Backend Engineering

LinkedIn: https://www.linkedin.com/in/anjali-yadav-464099257/ 
GitHub: https://github.com/AnjaliYadav-04

---

# ⭐ Why CorexRAG?

CorexRAG solves enterprise-grade RAG problems:

✔ Hallucination reduction  
✔ Better retrieval precision  
✔ Faster responses with cache  
✔ Secure SQL querying  
✔ Enterprise guardrails  
✔ Kubernetes-aware intelligence  
✔ Production-ready architecture  

---
